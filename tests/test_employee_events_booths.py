"""Testy modulu cashier_app.employee_events_booths pro udalosti a stanky zamestnancu."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT


def _mock_auth(employee):
    return patch('cashier_app.employee_events_booths.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# GET /api/employees/me/events/active
# ---------------------------------------------------------------------------

class TestGetActiveEvents:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.get('/api/employees/me/events/active')
            assert resp.status_code == 401

    @patch('cashier_app.employee_events_booths.get_pool')
    def test_admin_gets_all_events(self, mock_pool, client):
        events_list = [{'id': str(uuid4()), 'name': 'Event1'}]
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = events_list
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.get('/api/employees/me/events/active')
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)


# ---------------------------------------------------------------------------
# PUT /api/employees/me/events/select
# ---------------------------------------------------------------------------

class TestSelectEvent:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.put('/api/employees/me/events/select')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.put('/api/employees/me/events/select', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.put('/api/employees/me/events/select', data={
                'event': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.employee_events_booths.get_pool')
    def test_event_not_found(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.put('/api/employees/me/events/select', data={
                'event': str(uuid4()),
            })
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/employees/me/events/remove
# ---------------------------------------------------------------------------

class TestRemoveEvent:

    def test_removes_event_from_session(self, client):
        resp = client.delete('/api/employees/me/events/remove')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PUT /api/employees/me/events/booths/select
# ---------------------------------------------------------------------------

class TestSelectBooth:

    def test_unauthenticated(self, client):
        with _mock_auth(None), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select')
            assert resp.status_code == 401

    def test_no_event_selected(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=None):
            resp = client.put('/api/employees/me/events/booths/select')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_missing_booth_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_booth_id'

    def test_invalid_booth_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select', data={
                'booth': 'bad-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_id'


# ---------------------------------------------------------------------------
# DELETE /api/employees/me/events/booths/remove
# ---------------------------------------------------------------------------

class TestRemoveBooth:

    def test_removes_booth_from_session(self, client):
        resp = client.delete('/api/employees/me/events/booths/remove')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/employees/me/events/booths/active
# ---------------------------------------------------------------------------

class TestGetEventBooths:

    def test_unauthenticated(self, client):
        with _mock_auth(None), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=SAMPLE_EVENT):
            resp = client.get('/api/employees/me/events/booths/active')
            assert resp.status_code == 401

    def test_no_event_selected(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', return_value=None):
            resp = client.get('/api/employees/me/events/booths/active')
            assert resp.status_code == 400
