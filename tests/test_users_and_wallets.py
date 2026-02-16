"""Testy obsluznych funkci tras modulu cashier_app.users_and_wallets."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER, SAMPLE_BOOTH_SELLER,
)


def _mock_auth(employee):
    return patch('cashier_app.users_and_wallets.load_logged_in_employee', return_value=employee)


def _mock_event(event):
    return patch('cashier_app.users_and_wallets.load_selected_event', return_value=event)


def _mock_booth(booth):
    return patch('cashier_app.users_and_wallets.load_selected_booth', return_value=booth)


# ---------------------------------------------------------------------------
# GET /api/users
# ---------------------------------------------------------------------------

class TestGetUsers:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 401

    @patch('cashier_app.users_and_wallets.add_more_phone_number_info')
    @patch('cashier_app.users_and_wallets.get_pool')
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

        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.get('/api/users')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'users' in data

    def test_non_admin_no_event(self, client):
        with _mock_auth(REGULAR_EMPLOYEE), _mock_event(None), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_non_admin_no_booth(self, client):
        with _mock_auth(REGULAR_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(None):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_non_admin_wrong_booth_type(self, client):
        with _mock_auth(REGULAR_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/users')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'


# ---------------------------------------------------------------------------
# POST /api/users/create
# ---------------------------------------------------------------------------

class TestAddUser:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/create')
            assert resp.status_code == 401

    def test_missing_first_name(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': '',
                'last-name': 'Novak',
                'email': 'test@test.com',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_first_name'

    def test_missing_last_name(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': '',
                'email': 'test@test.com',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_last_name'

    def test_no_identifier_provided(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
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
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'email': 'bad-email',
            })
            assert resp.status_code == 400

    def test_phone_number_without_country_code(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/create', data={
                'first-name': 'Jan',
                'last-name': 'Novak',
                'phone-number': '601234567',
                'phone-number-country-code': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_country_code'

    @patch('cashier_app.users_and_wallets.get_pool')
    def test_successful_creation_with_email(self, mock_pool, client):
        user_id = uuid4()
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = {'id': user_id}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
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
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/edit')
            assert resp.status_code == 401

    def test_missing_user_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_user_id'

    def test_invalid_user_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/edit', data={'user-id': 'not-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'


# ---------------------------------------------------------------------------
# DELETE /api/users/delete
# ---------------------------------------------------------------------------

class TestDeleteUser:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.delete('/api/users/delete')
            assert resp.status_code == 401

    def test_missing_user_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.delete('/api/users/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_user_id'

    def test_invalid_user_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.delete('/api/users/delete', data={'user-id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    def test_non_admin_no_event(self, client):
        with _mock_auth(REGULAR_EMPLOYEE), _mock_event(None), _mock_booth(None):
            resp = client.delete('/api/users/delete')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'


# ---------------------------------------------------------------------------
# POST /api/users/wallets/create
# ---------------------------------------------------------------------------

class TestAddWallet:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/wallets/create')
            assert resp.status_code == 401

    def test_no_event(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/wallets/create')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_no_booth(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(None):
            resp = client.post('/api/users/wallets/create')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/users/wallets/create')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_invalid_user_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/create', data={
                'user-id': 'not-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    def test_missing_tag_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': '',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_missing_idempotency_key(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_balance_mismatch(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '100',
                'new-balance': '200',  # neodpovida
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'change_balance_by_and_new_balance_do_not_match'

    def test_negative_new_balance(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '-50',
                'new-balance': '-50',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'wallet_balance_czk_is_not_enough'


# ---------------------------------------------------------------------------
# POST /api/users/wallets/return
# ---------------------------------------------------------------------------

class TestReturnWallet:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(None), _mock_booth(None):
            resp = client.post('/api/users/wallets/return')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/users/wallets/return')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_tag_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/return', data={
                'tag-id': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_missing_idempotency_key(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/users/wallets/return', data={
                'tag-id': 'CARD1',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'
