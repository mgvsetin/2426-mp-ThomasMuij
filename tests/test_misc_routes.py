"""Tests for smaller route modules: reader_info, deleted pages, index, users deleted/restore."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER, set_session


# ---------------------------------------------------------------------------
# GET /api/reader/info
# ---------------------------------------------------------------------------

class TestReaderInfo:

    def test_unauthenticated(self, client):
        with patch('cashier_app.reader_info.load_logged_in_employee', return_value=None):
            resp = client.get('/api/reader/info')
            assert resp.status_code == 401

    def test_authenticated_returns_reader_info(self, client, app):
        with patch('cashier_app.reader_info.load_logged_in_employee', return_value=ADMIN_EMPLOYEE):
            resp = client.get('/api/reader/info')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'reader_info' in data


# ---------------------------------------------------------------------------
# GET /deleted/users  and  GET /deleted/events  (page routes)
# ---------------------------------------------------------------------------

class TestDeletedPages:

    def test_deleted_users_page(self, client):
        resp = client.get('/deleted/users')
        assert resp.status_code == 200

    def test_deleted_events_page(self, client):
        resp = client.get('/deleted/events')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /  (index page)
# ---------------------------------------------------------------------------

class TestIndexPage:

    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/users/deleted
# ---------------------------------------------------------------------------

class TestGetDeletedUsers:

    def _mock_auth(self, employee):
        return patch('cashier_app.users_and_wallets.load_logged_in_employee', return_value=employee)

    def test_unauthenticated(self, client):
        with self._mock_auth(None):
            resp = client.get('/api/users/deleted')
            assert resp.status_code == 401

    @patch('cashier_app.users_and_wallets.get_pool')
    def test_admin_gets_deleted_users(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with self._mock_auth(ADMIN_EMPLOYEE):
            with patch('cashier_app.users_and_wallets.add_more_phone_number_info'):
                resp = client.get('/api/users/deleted')
                assert resp.status_code == 200
                assert 'users' in resp.get_json()

    @patch('cashier_app.users_and_wallets.get_pool')
    def test_non_admin_without_booth_requires_event(self, mock_pool, client):
        """Non-admin non-manager without selected event gets 400."""
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None  # not a manager
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with self._mock_auth(REGULAR_EMPLOYEE):
            with patch('cashier_app.users_and_wallets.load_selected_event', return_value=None):
                with patch('cashier_app.users_and_wallets.load_selected_booth', return_value=None):
                    resp = client.get('/api/users/deleted')
                    assert resp.status_code == 400
                    assert resp.get_json()['error'] == 'no_selected_event'


# ---------------------------------------------------------------------------
# POST /api/users/restore
# ---------------------------------------------------------------------------

class TestRestoreUser:

    def _mock_auth(self, employee):
        return patch('cashier_app.users_and_wallets.load_logged_in_employee', return_value=employee)

    def test_unauthenticated(self, client):
        with self._mock_auth(None):
            resp = client.post('/api/users/restore', data={})
            assert resp.status_code == 401

    def test_invalid_user_id(self, client):
        with self._mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/users/restore', data={'user-id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    @patch('cashier_app.users_and_wallets.get_pool')
    def test_user_not_found(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with self._mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/users/restore', data={'user-id': str(uuid4())})
            assert resp.status_code == 404
            assert resp.get_json()['error'] == 'user_not_found'
