"""Testy obsluznych funkci tras modulu cashier_app.employees."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT,
    mock_auth, mock_event,
)


# ---------------------------------------------------------------------------
# GET /api/employees
# ---------------------------------------------------------------------------

class TestGetEmployees:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get('/api/employees')
            assert resp.status_code == 401

    @patch('cashier_app.employees.get_pool')
    def test_admin_gets_employees(self, mock_pool, client):
        employees_list = [
            {'id': str(uuid4()), 'username': 'admin', 'email': 'a@b.com',
             'is_admin': True, 'created_by': None, 'created_at': '2025-01-01'}
        ]
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = employees_list
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.get('/api/employees')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'employees' in data
            assert len(data['employees']) == 1

    @patch('cashier_app.employees.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_mgr, client):
        with mock_auth(REGULAR_EMPLOYEE), mock_event(SAMPLE_EVENT):
            resp = client.get('/api/employees')
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/employees/create
# ---------------------------------------------------------------------------

class TestAddEmployee:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/employees/create')
            assert resp.status_code == 401

    def test_non_admin_forbidden(self, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/employees/create')
            assert resp.status_code == 403

    def test_missing_username(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': '',
                'email': 'test@test.com',
                'password': 'TestPass1!',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_username'

    def test_missing_email(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': 'testuser',
                'email': '',
                'password': 'TestPass1!',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_email'

    def test_missing_password(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': 'testuser',
                'email': 'test@test.com',
                'password': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_password'

    def test_invalid_username(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': 'ab',  # prilis kratke
                'email': 'test@test.com',
                'password': 'TestPass1!',
            })
            assert resp.status_code == 400

    def test_invalid_email(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': 'testuser',
                'email': 'not-an-email',
                'password': 'TestPass1!',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_email'

    def test_weak_password(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/create', data={
                'username': 'testuser',
                'email': 'test@test.com',
                'password': '123',
            })
            assert resp.status_code == 400

    def test_is_admin_parsing_true(self, client):
        with mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.employees.get_pool') as mock_pool, \
             patch('cashier_app.employees.save_change'):

            new_emp = {
                'id': str(uuid4()), 'username': 'newadmin', 'email': 'new@test.com',
                'is_admin': True, 'password_hash': 'xxx', 'created_by': ADMIN_EMPLOYEE['id'],
                'created_at': '2025-01-01', 'deleted_at': None,
            }
            mock_cur = MagicMock()
            mock_cur.execute.return_value.fetchone.return_value = new_emp
            mock_conn = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

            resp = client.post('/api/employees/create', data={
                'username': 'newadmin',
                'email': 'new@test.com',
                'password': 'SecureP@ss1',
                'is-admin': 'true',
            })
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/employees/edit
# ---------------------------------------------------------------------------

class TestEditEmployee:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/employees/edit')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/employees/edit', data={'id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'

    def test_non_admin_forbidden(self, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/employees/edit', data={'id': str(uuid4())})
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/employees/delete
# ---------------------------------------------------------------------------

class TestDeleteEmployee:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.delete('/api/employees/delete')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/employees/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/employees/delete', data={'id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'

    def test_non_admin_cannot_delete_other(self, client):
        other_id = str(uuid4())
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.delete('/api/employees/delete', data={'id': other_id})
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /employees/manager
# ---------------------------------------------------------------------------

class TestEmployeesManagerPage:

    def test_returns_html(self, client):
        resp = client.get('/employees/manager')
        assert resp.status_code == 200


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestEmployeesDB:
    """Integrační testy zaměstnanců s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.employees.get_pool', return_value=db_pool))
        return stack

    def test_create_employee(self, client, db_pool, db_cursor, db_employee_admin):
        """Vytvoření zaměstnance přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/employees/create', data={
                'username': 'new_employee',
                'email': 'new_employee@test.com',
                'password': 'SecureP@ss1',
                'is-admin': 'false',
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM employees WHERE username = 'new_employee' AND deleted_at IS NULL")
        emp = db_cursor.fetchone()
        assert emp is not None
        assert emp['email'] == 'new_employee@test.com'
        assert emp['is_admin'] is False
        assert emp['password_hash'].startswith('$argon2id$')

    def test_create_employee_duplicate_username(self, client, db_pool, db_cursor, db_employee_admin):
        """Duplicitní username vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/employees/create', data={
                'username': db_employee_admin['username'],
                'email': 'unique@test.com',
                'password': 'SecureP@ss1',
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'username_taken'

    def test_create_employee_duplicate_email(self, client, db_pool, db_cursor, db_employee_admin):
        """Duplicitní email vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/employees/create', data={
                'username': 'unique_user',
                'email': db_employee_admin['email'],
                'password': 'SecureP@ss1',
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'email_taken'

    def test_edit_employee(self, client, db_pool, db_cursor,
                           db_employee_admin, db_employee_regular):
        """Úprava zaměstnance přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/employees/edit', data={
                'id': str(db_employee_regular['id']),
                'username': 'updated_cashier',
                'email': 'updated_cashier@test.com',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT username, email FROM employees WHERE id = %s",
                          (db_employee_regular['id'],))
        emp = db_cursor.fetchone()
        assert emp['username'] == 'updated_cashier'
        assert emp['email'] == 'updated_cashier@test.com'

    def test_delete_employee(self, client, db_pool, db_cursor,
                             db_employee_admin, db_employee_regular, db_employee_role):
        """Smazání zaměstnance (soft-delete) včetně rolí."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/employees/delete', data={
                'id': str(db_employee_regular['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM employees WHERE id = %s",
                          (db_employee_regular['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_cannot_delete_last_admin(self, client, db_pool, db_cursor, db_employee_admin):
        """Nelze smazat posledního admina."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/employees/delete', data={
                'id': str(db_employee_admin['id']),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'can_not_delete_last_admin'

    def test_get_employees(self, client, db_pool, db_cursor, db_employee_admin):
        """Získání seznamu zaměstnanců."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.get('/api/employees')
            assert resp.status_code == 200
            employees = resp.get_json()['employees']
            assert any(str(db_employee_admin['id']) == e['id'] for e in employees)
