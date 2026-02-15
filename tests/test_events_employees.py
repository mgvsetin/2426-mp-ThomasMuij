"""Tests for cashier_app.events.event_employees route handlers."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT


def _mock_auth(employee):
    return patch('cashier_app.events.event_employees.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# POST /api/events/employees/assign-manager
# ---------------------------------------------------------------------------

class TestAssignManager:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/employees/assign-manager')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={'event-id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    def test_missing_username_or_email(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={
                'event-id': str(uuid4()),
                'username-or-email': ''
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_username_or_email'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={
                'event-id': str(uuid4()),
                'username-or-email': 'someone'
            })
            assert resp.status_code == 403
            assert resp.get_json()['error'] == 'insufficient_privileges'


# ---------------------------------------------------------------------------
# POST /api/events/employees/assign-employee
# ---------------------------------------------------------------------------

class TestAssignEmployee:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/employees/assign-employee')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={'event-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    def test_missing_username_or_email(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(uuid4()),
                'username-or-email': ''
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_username_or_email'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(uuid4()),
                'username-or-email': 'someone'
            })
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/events/employees/unassign
# ---------------------------------------------------------------------------

class TestUnassignEmployee:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/employees/unassign')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={'event-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
            })
            assert resp.status_code == 403

    @patch('cashier_app.events.event_employees.get_pool')
    @patch('cashier_app.events.event_employees.sync_employee_event_booth_roles', return_value=[])
    @patch('cashier_app.events.event_employees.save_change')
    def test_missing_employee_id(self, mock_save, mock_sync, mock_pool, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    @patch('cashier_app.events.event_employees.get_pool')
    @patch('cashier_app.events.event_employees.sync_employee_event_booth_roles', return_value=[])
    @patch('cashier_app.events.event_employees.save_change')
    def test_invalid_employee_id(self, mock_save, mock_sync, mock_pool, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
                'id': 'not-a-uuid'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'
