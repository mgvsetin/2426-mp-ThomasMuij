"""Testy autentizacniho modulu cashier_app.auth."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import set_session, ADMIN_EMPLOYEE


class TestLoginEndpoint:

    @patch('cashier_app.auth.employee_password_is_correct', return_value=True)
    @patch('cashier_app.auth.get_employee_id', return_value=uuid4())
    def test_successful_login(self, mock_get_id, mock_password, client):
        response = client.post('/api/auth/login', data={
            'username-email': 'admin',
            'password': 'testpassword',
        })
        assert response.status_code == 201
        data = response.get_json()
        assert 'redirect_url' in data

    @patch('cashier_app.auth.get_employee_id', return_value=None)
    def test_login_with_invalid_credentials(self, mock_get_id, client):
        response = client.post('/api/auth/login', data={
            'username-email': 'nonexistent',
            'password': 'wrong',
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'invalid_credentials'

    @patch('cashier_app.auth.employee_password_is_correct', return_value=False)
    @patch('cashier_app.auth.get_employee_id', return_value=uuid4())
    def test_login_wrong_password(self, mock_get_id, mock_password, client):
        response = client.post('/api/auth/login', data={
            'username-email': 'admin',
            'password': 'wrongpass',
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'invalid_credentials'

    @patch('cashier_app.auth.employee_password_is_correct', return_value=True)
    @patch('cashier_app.auth.get_employee_id', return_value=uuid4())
    def test_login_with_remember_me(self, mock_get_id, mock_password, client):
        response = client.post('/api/auth/login', data={
            'username-email': 'admin',
            'password': 'testpassword',
            'remember-me': 'on',
        })
        assert response.status_code == 201

    @patch('cashier_app.auth.get_employee_id', return_value=None)
    def test_login_empty_fields(self, mock_get_id, client):
        response = client.post('/api/auth/login', data={
            'username-email': '',
            'password': '',
        })
        assert response.status_code == 401


class TestLogoutEndpoint:

    def test_logout_redirects_to_login(self, client):
        response = client.get('/api/auth/logout', follow_redirects=False)
        assert response.status_code == 302


class TestGetLoginPage:

    def test_login_page_returns_html(self, client):
        response = client.get('/auth/login')
        assert response.status_code == 200


class TestLoadLoggedInEmployee:

    @patch('cashier_app.auth.get_pool')
    def test_returns_employee_when_session_has_id(self, mock_pool, app):
        employee_id = str(uuid4())
        employee_data = {
            'id': employee_id,
            'username': 'admin',
            'email': 'admin@test.com',
            'is_admin': True,
        }

        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = employee_data
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        from cashier_app.auth import load_logged_in_employee

        with app.test_request_context():
            from flask import session, g
            session['employee_id'] = employee_id
            result = load_logged_in_employee()
            assert result == employee_data

    def test_returns_none_when_no_session(self, app):
        from cashier_app.auth import load_logged_in_employee

        with app.test_request_context():
            result = load_logged_in_employee()
            assert result is None


class TestGetEmployeeId:

    @patch('cashier_app.auth.get_pool')
    def test_returns_id_for_existing_user(self, mock_pool, app):
        uid = uuid4()
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = {'id': uid}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        from cashier_app.auth import get_employee_id

        with app.app_context():
            result = get_employee_id('admin')
            assert result == uid

    @patch('cashier_app.auth.get_pool')
    def test_returns_none_for_nonexistent_user(self, mock_pool, app):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        from cashier_app.auth import get_employee_id

        with app.app_context():
            result = get_employee_id('nonexistent')
            assert result is None
