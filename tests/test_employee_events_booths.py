"""Testy modulu cashier_app.employee_events_booths pro udalosti a stanky zamestnancu."""

import pytest
from uuid import uuid4
from unittest.mock import patch
from flask import g
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT,
    mock_auth, mock_auth_db, mock_event_db,
)


# ---------------------------------------------------------------------------
# GET /api/employees/me/events/active
# ---------------------------------------------------------------------------

class TestGetActiveEvents:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get('/api/employees/me/events/active')
            assert resp.status_code == 401

    @pytest.mark.db
    def test_admin_gets_all_events(self, client, db_pool, db_employee_admin, db_event):
        with mock_auth_db(db_employee_admin), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            resp = client.get('/api/employees/me/events/active')
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]['name'] == 'Test Event'


# ---------------------------------------------------------------------------
# PUT /api/employees/me/events/select
# ---------------------------------------------------------------------------

class TestSelectEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.put('/api/employees/me/events/select')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.put('/api/employees/me/events/select', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.put('/api/employees/me/events/select', data={
                'event': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @pytest.mark.db
    def test_event_not_found(self, client, db_pool, db_employee_admin):
        with mock_auth_db(db_employee_admin), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            resp = client.put('/api/employees/me/events/select', data={
                'event': str(uuid4()),
            })
            assert resp.status_code == 404

    @pytest.mark.db
    def test_select_event_success(self, client, db_pool, db_employee_admin, db_event):
        with mock_auth_db(db_employee_admin), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            resp = client.put('/api/employees/me/events/select', data={
                'event': str(db_event['id']),
            })
            assert resp.status_code == 200

            with client.session_transaction() as sess:
                assert sess['event_id'] == str(db_event['id'])


# ---------------------------------------------------------------------------
# DELETE /api/employees/me/events/remove
# ---------------------------------------------------------------------------

class TestRemoveEvent:

    def test_removes_event_from_session(self, client):
        resp = client.delete('/api/employees/me/events/remove')
        assert resp.status_code == 200

    @pytest.mark.db
    def test_unselect_event_success(self, client, db_pool, db_employee_admin, db_event):
        with mock_auth_db(db_employee_admin), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            # First select an event
            resp = client.put('/api/employees/me/events/select', data={
                'event': str(db_event['id']),
            })
            assert resp.status_code == 200

            # Now remove it
            resp = client.delete('/api/employees/me/events/remove')
            assert resp.status_code == 200

            with client.session_transaction() as sess:
                assert 'event_id' not in sess


# ---------------------------------------------------------------------------
# PUT /api/employees/me/events/booths/select
# ---------------------------------------------------------------------------

class TestSelectBooth:

    def test_unauthenticated(self, client):
        with mock_auth(None), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', SAMPLE_EVENT) or SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select')
            assert resp.status_code == 401

    def test_no_event_selected(self, client):
        with mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', None) or None):
            resp = client.put('/api/employees/me/events/booths/select')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_missing_booth_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', SAMPLE_EVENT) or SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_booth_id'

    def test_invalid_booth_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', SAMPLE_EVENT) or SAMPLE_EVENT):
            resp = client.put('/api/employees/me/events/booths/select', data={
                'booth': 'bad-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_id'

    @pytest.mark.db
    def test_select_booth_success(self, client, db_pool, db_employee_admin, db_event, db_booth_cashier):
        with mock_auth_db(db_employee_admin), \
             mock_event_db(db_event), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            resp = client.put('/api/employees/me/events/booths/select', data={
                'booth': str(db_booth_cashier['id']),
            })
            assert resp.status_code == 200
            assert resp.get_json()['booth_type'] == 'cashier'

            with client.session_transaction() as sess:
                assert sess['booth_id'] == str(db_booth_cashier['id'])


# ---------------------------------------------------------------------------
# DELETE /api/employees/me/events/booths/remove
# ---------------------------------------------------------------------------

class TestRemoveBooth:

    def test_removes_booth_from_session(self, client):
        resp = client.delete('/api/employees/me/events/booths/remove')
        assert resp.status_code == 200

    @pytest.mark.db
    def test_unselect_booth_success(self, client, db_pool, db_employee_admin, db_event, db_booth_cashier):
        with mock_auth_db(db_employee_admin), \
             mock_event_db(db_event), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            # First select a booth
            resp = client.put('/api/employees/me/events/booths/select', data={
                'booth': str(db_booth_cashier['id']),
            })
            assert resp.status_code == 200

            # Now remove it
            resp = client.delete('/api/employees/me/events/booths/remove')
            assert resp.status_code == 200

            with client.session_transaction() as sess:
                assert 'booth_id' not in sess


# ---------------------------------------------------------------------------
# GET /api/employees/me/events/booths/active
# ---------------------------------------------------------------------------

class TestGetEventBooths:

    def test_unauthenticated(self, client):
        with mock_auth(None), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', SAMPLE_EVENT) or SAMPLE_EVENT):
            resp = client.get('/api/employees/me/events/booths/active')
            assert resp.status_code == 401

    def test_no_event_selected(self, client):
        with mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employee_events_booths.load_selected_event', side_effect=lambda: setattr(g, 'event', None) or None):
            resp = client.get('/api/employees/me/events/booths/active')
            assert resp.status_code == 400

    @pytest.mark.db
    def test_get_event_booths_success(self, client, db_pool, db_employee_admin, db_event, db_booth_cashier, db_booth_seller):
        with mock_auth_db(db_employee_admin), \
             mock_event_db(db_event), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool):
            resp = client.get('/api/employees/me/events/booths/active')
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            assert len(data) == 2
            booth_ids = {b['id'] for b in data}
            assert str(db_booth_cashier['id']) in booth_ids
            assert str(db_booth_seller['id']) in booth_ids
