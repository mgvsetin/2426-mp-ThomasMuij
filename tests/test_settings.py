"""Testy pro obslužné funkce tras modulu cashier_app.settings (nastavení)."""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE


def _mock_auth(employee):
    return patch('cashier_app.settings.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# GET /settings (stránka)
# ---------------------------------------------------------------------------

class TestSettingsPage:

    def test_page_renders(self, client):
        resp = client.get('/settings')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/settings/profile
# ---------------------------------------------------------------------------

class TestGetProfile:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.get('/api/settings/profile')
            assert resp.status_code == 401

    def test_returns_employee_data(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.get('/api/settings/profile')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['employee']['username'] == ADMIN_EMPLOYEE['username']
            assert data['employee']['email'] == ADMIN_EMPLOYEE['email']
            assert data['employee']['is_admin'] == ADMIN_EMPLOYEE['is_admin']

    def test_returns_non_admin_employee(self, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.get('/api/settings/profile')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['employee']['is_admin'] is False


# ---------------------------------------------------------------------------
# POST /api/settings/update-profile
# ---------------------------------------------------------------------------

class TestUpdateProfile:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/settings/update-profile', data={})
            assert resp.status_code == 401

    def test_missing_current_password(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/settings/update-profile', data={
                'new-password': 'NewPass123'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_current_password'

    def test_nothing_to_update(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/settings/update-profile', data={
                'current-password': 'secret123'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'nothing_to_update'

    @patch('cashier_app.settings.employee_password_is_correct', return_value=False)
    def test_wrong_current_password(self, mock_check, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/settings/update-profile', data={
                'current-password': 'wrongpassword',
                'new-password': 'NewPass123'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_current_password'

    # @patch('cashier_app.settings.employee_password_is_correct', return_value=True)
    # def test_invalid_username(self, mock_check, client):
    #     with _mock_auth(ADMIN_EMPLOYEE):
    #         resp = client.post('/api/settings/update-profile', data={
    #             'current-password': 'correctpassword',
    #             'username': 'a'  # too short
    #         })
    #         assert resp.status_code == 400

    @patch('cashier_app.settings.employee_password_is_correct', return_value=True)
    def test_passwords_do_not_match(self, mock_check, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/settings/update-profile', data={
                'current-password': 'correctpassword',
                'new-password': 'NewPass123!',
                'confirm-password': 'DifferentPass123!'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'passwords_do_not_match'

    @patch('cashier_app.settings.employee_password_is_correct', return_value=True)
    def test_missing_new_password_when_confirm_given(self, mock_check, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/settings/update-profile', data={
                'current-password': 'correctpassword',
                'new-password': '',
                'confirm-password': 'SomePass123!'
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_new_password'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================


def _mock_auth_db(employee_dict):
    """Mock auth pro settings s reálnými DB daty."""
    emp = {k: str(v) if hasattr(v, 'hex') else v for k, v in employee_dict.items()}
    return patch('cashier_app.settings.load_logged_in_employee', return_value=emp)


@pytest.mark.db
class TestUpdateProfileDB:
    """Integrační testy aktualizace profilu s reálnou DB."""

    def test_successful_password_update(self, client, db_pool, db_cursor, db_employee_admin):
        """Úspěšná změna hesla přes API změní hash v DB."""
        old_hash = db_employee_admin['password_hash']

        with _mock_auth_db(db_employee_admin), \
             patch('cashier_app.settings.employee_password_is_correct', return_value=True), \
             patch('cashier_app.settings.get_pool', return_value=db_pool):
            resp = client.post('/api/settings/update-profile', data={
                'current-password': 'OldPass123!',
                'new-password': 'NewSecureP@ss1',
                'confirm-password': 'NewSecureP@ss1',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT password_hash FROM employees WHERE id = %s",
                          (db_employee_admin['id'],))
        emp = db_cursor.fetchone()
        assert emp['password_hash'] != old_hash
        assert emp['password_hash'].startswith('$argon2id$')
