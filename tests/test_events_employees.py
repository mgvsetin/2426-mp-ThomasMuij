"""Testy pro obslužné funkce tras modulu cashier_app.events.event_employees."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT, mock_auth


# ---------------------------------------------------------------------------
# POST /api/events/employees/assign-manager
# ---------------------------------------------------------------------------

class TestAssignManager:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/employees/assign-manager')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={'event-id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    def test_missing_username_or_email(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-manager', data={
                'event-id': str(uuid4()),
                'username-or-email': ''
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_username_or_email'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with mock_auth(REGULAR_EMPLOYEE):
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
        with mock_auth(None):
            resp = client.post('/api/events/employees/assign-employee')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={'event-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    def test_missing_username_or_email(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(uuid4()),
                'username-or-email': ''
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_username_or_email'

    def test_missing_booths(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(uuid4()),
                'username-or-email': 'someone',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_booths'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(uuid4()),
                'username-or-email': 'someone',
                'booths': str(uuid4()),
            })
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/events/employees/unassign
# ---------------------------------------------------------------------------

class TestUnassignEmployee:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/employees/unassign')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={'event-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.event_employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_manager, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
            })
            assert resp.status_code == 403

    @patch('cashier_app.events.event_employees.get_pool')
    @patch('cashier_app.events.event_employees.sync_employee_event_booth_roles', return_value=[])
    @patch('cashier_app.events.event_employees.save_change')
    def test_missing_employee_id(self, mock_save, mock_sync, mock_pool, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    @patch('cashier_app.events.event_employees.get_pool')
    @patch('cashier_app.events.event_employees.sync_employee_event_booth_roles', return_value=[])
    @patch('cashier_app.events.event_employees.save_change')
    def test_invalid_employee_id(self, mock_save, mock_sync, mock_pool, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(uuid4()),
                'id': 'not-a-uuid'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestEventEmployeesDB:
    """Integrační testy přiřazení zaměstnanců k událostem s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.event_employees.get_pool', return_value=db_pool))
        return stack

    def test_assign_manager(self, client, db_pool, db_cursor,
                             db_employee_admin, db_event, db_employee_regular):
        """Přiřazení zaměstnance jako manažera události."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/employees/assign-manager', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_regular['username'],
            })
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id IS NULL
        """, (db_employee_regular['id'], db_event['id']))
        assert db_cursor.fetchone() is not None

    def test_assign_employee_to_booths(self, client, db_pool, db_cursor,
                                        db_employee_admin, db_event,
                                        db_employee_regular, db_booth_seller):
        """Přiřazení zaměstnance ke stánku."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_regular['username'],
                'booths': str(db_booth_seller['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id = %s
        """, (db_employee_regular['id'], db_event['id'], db_booth_seller['id']))
        assert db_cursor.fetchone() is not None

    def test_cannot_assign_admin(self, client, db_pool, db_cursor,
                                  db_employee_admin, db_event):
        """Administrátor nemůže být přiřazen jako manažer."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/employees/assign-manager', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_admin['username'],
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'can_not_assign_admin'

    def test_manager_cannot_be_assigned_to_booths(self, client, db_pool, db_cursor,
                                                    db_employee_admin, db_event,
                                                    db_employee_regular, db_booth_seller):
        """Manažer nemůže být přiřazen ke stánkům."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.post('/api/events/employees/assign-manager', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_regular['username'],
            })
            resp = client.post('/api/events/employees/assign-employee', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_regular['username'],
                'booths': str(db_booth_seller['id']),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'can_not_assign_manager_to_booths'

    def test_unassign_employee(self, client, db_pool, db_cursor,
                                db_employee_admin, db_event,
                                db_employee_regular, db_booth_seller):
        """Odebrání zaměstnance z události."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.post('/api/events/employees/assign-employee', data={
                'event-id': str(db_event['id']),
                'username-or-email': db_employee_regular['username'],
                'booths': str(db_booth_seller['id']),
            })
            resp = client.post('/api/events/employees/unassign', data={
                'event-id': str(db_event['id']),
                'id': str(db_employee_regular['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s
        """, (db_employee_regular['id'], db_event['id']))
        assert db_cursor.fetchone() is None
