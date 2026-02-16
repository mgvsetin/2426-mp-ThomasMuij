"""Testy modulu cashier_app.session_api pro spravu relace."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, SAMPLE_EVENT, SAMPLE_BOOTH_SELLER


class TestSessionInfo:

    @patch('cashier_app.session_api.load_selected_booth', return_value=None)
    @patch('cashier_app.session_api.load_selected_event', return_value=None)
    @patch('cashier_app.session_api.load_logged_in_employee', return_value=None)
    def test_no_session(self, mock_emp, mock_evt, mock_booth, client):
        resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee'] is None
        assert data['event'] is None
        assert data['booth'] is None

    @patch('cashier_app.session_api.get_pool')
    @patch('cashier_app.session_api.load_selected_booth', return_value=None)
    @patch('cashier_app.session_api.load_selected_event', return_value=None)
    @patch('cashier_app.session_api.load_logged_in_employee', return_value=ADMIN_EMPLOYEE)
    def test_employee_only(self, mock_emp, mock_evt, mock_booth, mock_pool, client):
        resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee'] is not None
        assert data['employee']['username'] == 'admin'
        assert data['employee']['is_admin'] is True
        assert data['event'] is None

    @patch('cashier_app.session_api.get_pool')
    @patch('cashier_app.session_api.load_selected_booth', return_value=SAMPLE_BOOTH_SELLER)
    @patch('cashier_app.session_api.load_selected_event', return_value=SAMPLE_EVENT)
    @patch('cashier_app.session_api.load_logged_in_employee', return_value=ADMIN_EMPLOYEE)
    def test_full_session(self, mock_emp, mock_evt, mock_booth, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None  # neni manazer
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee']['username'] == 'admin'
        assert data['event']['name'] == 'TestEvent'
        assert data['booth']['name'] == 'Booth1'
        assert data['booth']['booth_type'] == 'seller'
