"""Testy obsluznych funkci tras modulu cashier_app.users."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER, SAMPLE_BOOTH_SELLER,
    mock_auth,
)


def _mock_event(event):
    return patch('cashier_app.users.load_selected_event', return_value=event)


def _mock_booth(booth):
    return patch('cashier_app.users.load_selected_booth', return_value=booth)


# ---------------------------------------------------------------------------
# GET /api/users
# ---------------------------------------------------------------------------

class TestGetUsers:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 401

    @patch('cashier_app.users.add_more_phone_number_info')
    @patch('cashier_app.users.get_pool')
    def test_admin_gets_users(self, mock_pool, mock_phone, client):
        users_list = [
            {'id': str(uuid4()), 'first_name': 'Jan', 'last_name': 'Novak',
             'email': 'j@n.com', 'phone_number': None, 'other_identifier': None}
        ]
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = users_list
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.get('/api/users')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'users' in data

    def test_non_admin_no_event(self, client):
        with mock_auth(REGULAR_EMPLOYEE), _mock_event(None), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_non_admin_no_booth(self, client):
        with mock_auth(REGULAR_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_non_admin_wrong_booth_type(self, client):
        with mock_auth(REGULAR_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'


# ---------------------------------------------------------------------------
# POST /api/users/create
# ---------------------------------------------------------------------------

class TestAddUser:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/create')
            assert resp.status_code == 401

    def test_missing_first_name(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': '',
                'last-name': 'Novak',
                'email': 'test@test.com',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_first_name'

    def test_missing_last_name(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': '',
                'email': 'test@test.com',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_last_name'

    def test_no_identifier_provided(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'email': '',
                'phone-number': '',
                'other-identifier': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'at_least_one_of_email_phone_number_other_identifier_is_required'

    def test_invalid_email(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'email': 'bad-email',
            })
            assert resp.status_code == 400

    def test_phone_number_without_country_code(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'phone-number': '601234567',
                'phone-number-country-code': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_country_code'

    @patch('cashier_app.users.get_pool')
    def test_successful_creation_with_email(self, mock_pool, client):
        user_id = uuid4()
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = {'id': user_id}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'email': 'jan@novak.cz',
            })
            assert resp.status_code == 200
            assert 'user_id' in resp.get_json()


# ---------------------------------------------------------------------------
# POST /api/users/edit
# ---------------------------------------------------------------------------

class TestEditUser:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/edit')
            assert resp.status_code == 401

    def test_missing_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_user_id'

    def test_invalid_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/edit', data={'user-id': 'not-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'


# ---------------------------------------------------------------------------
# DELETE /api/users/delete
# ---------------------------------------------------------------------------

class TestDeleteUser:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.delete('/api/users/delete')
            assert resp.status_code == 401

    def test_missing_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.delete('/api/users/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_user_id'

    def test_invalid_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.delete('/api/users/delete', data={'user-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    def test_non_admin_no_event(self, client):
        with mock_auth(REGULAR_EMPLOYEE), _mock_event(None), _mock_booth(None):
            resp = client.delete('/api/users/delete')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'


# ---------------------------------------------------------------------------
# GET /api/users/deleted
# ---------------------------------------------------------------------------

class TestGetDeletedUsers:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get('/api/users/deleted')
            assert resp.status_code == 401

    @patch('cashier_app.users.get_pool')
    def test_admin_gets_deleted_users(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE):
            with patch('cashier_app.users.add_more_phone_number_info'):
                resp = client.get('/api/users/deleted')
                assert resp.status_code == 200
                assert 'users' in resp.get_json()

    @patch('cashier_app.users.get_pool')
    def test_non_admin_without_booth_requires_event(self, mock_pool, client):
        """Ne-admin, ne-manažer bez vybrané akce dostane 400."""
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None  # není manažer
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(REGULAR_EMPLOYEE):
            with _mock_event(None), _mock_booth(None):
                resp = client.get('/api/users/deleted')
                assert resp.status_code == 400
                assert resp.get_json()['error'] == 'no_selected_event'


# ---------------------------------------------------------------------------
# POST /api/users/restore
# ---------------------------------------------------------------------------

class TestRestoreUser:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/users/restore', data={})
            assert resp.status_code == 401

    def test_invalid_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/users/restore', data={'user-id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    @patch('cashier_app.users.get_pool')
    def test_user_not_found(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/users/restore', data={'user-id': str(uuid4())})
            assert resp.status_code == 404
            assert resp.get_json()['error'] == 'user_not_found'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db, mock_booth_db


@pytest.mark.db
class TestUsersDB:
    """Integrační testy uživatelů s reálnou DB."""

    def _pool_patches(self, db_pool):
        """Vrátí kontextový manažer pro patchování get_pool ve všech modulech users používá."""
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.users.get_pool', return_value=db_pool))
        return stack

    def test_create_user(self, client, db_pool, db_cursor, db_employee_admin):
        """Vytvoření uživatele přes API a ověření v DB."""
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jana',
                'last-name': 'Novakova',
                'email': 'jana@novakova.cz',
            })
            assert resp.status_code == 200
            user_id = resp.get_json()['user_id']

        db_cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = db_cursor.fetchone()
        assert user is not None
        assert user['first_name'] == 'Jana'
        assert user['last_name'] == 'Novakova'
        assert user['email'] == 'jana@novakova.cz'

    def test_create_user_duplicate_email(self, client, db_pool, db_cursor,
                                         db_employee_admin, db_user):
        """Duplicitní email vrátí 409."""
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jiny',
                'last-name': 'Clovek',
                'email': db_user['email'],
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'user_email_taken'

    def test_edit_user(self, client, db_pool, db_cursor, db_employee_admin, db_user):
        """Úprava uživatele přes API."""
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.post('/api/users/edit', data={
                'user-id': str(db_user['id']),
                'first-name': 'Updated',
                'last-name': 'Name',
                'email': 'updated@email.cz',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT first_name, last_name, email FROM users WHERE id = %s",
                          (db_user['id'],))
        user = db_cursor.fetchone()
        assert user['first_name'] == 'Updated'
        assert user['last_name'] == 'Name'
        assert user['email'] == 'updated@email.cz'

    def test_delete_user(self, client, db_pool, db_cursor, db_employee_admin, db_user):
        """Smazání uživatele (soft-delete)."""
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.delete('/api/users/delete', data={
                'user-id': str(db_user['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM users WHERE id = %s", (db_user['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_delete_user_cascades_wallets(self, client, db_pool, db_cursor,
                                          db_employee_admin, db_wallet):
        """Smazání uživatele kaskádově smaže peněženky."""
        owner_id = db_wallet['owner_id']
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.delete('/api/users/delete', data={
                'user-id': str(owner_id),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM wallets WHERE id = %s", (db_wallet['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_get_users(self, client, db_pool, db_cursor, db_employee_admin, db_user):
        """Získání seznamu uživatelů."""
        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.get('/api/users')
            assert resp.status_code == 200
            users = resp.get_json()['users']
            assert any(u['id'] == str(db_user['id']) for u in users)

    def test_get_deleted_users(self, client, db_pool, db_cursor, db_employee_admin, db_user):
        """Získání seznamu smazaných uživatelů."""
        # Nejdříve smažeme uživatele
        db_cursor.execute("UPDATE users SET deleted_at = now() WHERE id = %s", (db_user['id'],))

        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.get('/api/users/deleted')
            assert resp.status_code == 200
            users = resp.get_json()['users']
            assert any(u['id'] == str(db_user['id']) for u in users)

    def test_restore_user(self, client, db_pool, db_cursor, db_employee_admin, db_user):
        """Obnovení smazaného uživatele."""
        db_cursor.execute("UPDATE users SET deleted_at = now() WHERE id = %s", (db_user['id'],))

        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.post('/api/users/restore', data={
                'user-id': str(db_user['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM users WHERE id = %s", (db_user['id'],))
        assert db_cursor.fetchone()['deleted_at'] is None

    def test_restore_user_force_email_conflict(self, client, db_pool, db_cursor,
                                                db_employee_admin, db_user):
        """Obnovení s force=true vyřeší emailový konflikt přidáním suffixu."""
        original_email = db_user['email']
        # Smažeme uživatele
        db_cursor.execute("UPDATE users SET deleted_at = now() WHERE id = %s", (db_user['id'],))
        # Vytvoříme nového uživatele se stejným emailem
        db_cursor.execute("""
            INSERT INTO users (first_name, last_name, email)
            VALUES ('Conflict', 'User', %s)
        """, (original_email,))

        with mock_auth_db(db_employee_admin), self._pool_patches(db_pool):
            resp = client.post('/api/users/restore', data={
                'user-id': str(db_user['id']),
                'force': 'true',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT email, deleted_at FROM users WHERE id = %s", (db_user['id'],))
        restored = db_cursor.fetchone()
        assert restored['deleted_at'] is None
        # Email by měl být upraven (přidán suffix)
        assert restored['email'] != original_email
        assert restored['email'].startswith(original_email.split('@')[0])
