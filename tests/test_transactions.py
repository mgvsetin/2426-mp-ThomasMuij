"""Testy obsluznych funkci tras modulu cashier_app.transactions."""

import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    set_session, ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    SAMPLE_EVENT, SAMPLE_BOOTH_SELLER, SAMPLE_BOOTH_CASHIER,
    mock_auth, mock_event, mock_booth,
    mock_auth_db, mock_event_db, mock_booth_db,
)


# ---------------------------------------------------------------------------
# make-payment
# ---------------------------------------------------------------------------

class TestMakePayment:

    def test_unauthenticated(self, client):
        with mock_auth(None), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 401

    def test_no_selected_event(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(None), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_no_selected_booth(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(None):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-100',
                'products-info': '[]',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_missing_tag_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': '',
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_invalid_amount(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': 'abc',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'amount_czk_must_be_a_number'

    def test_non_integer_amount(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '10.5',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'amount_czk_must_be_a_whole_number'

    def test_amount_too_low(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-1000001',
                'idempotency-key': str(uuid4()),
                'products-info': '[]',
            })
            assert resp.status_code == 400

    def test_amount_too_high(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '1000001',
                'idempotency-key': str(uuid4()),
                'products-info': '[]',
            })
            assert resp.status_code == 400

    def test_invalid_products_info_json(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
                'products-info': 'not json',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_products_info'

    def test_products_total_mismatch(self, client):
        products = [{'id': str(uuid4()), 'name': 'Beer', 'price': 50, 'quantity': 2}]
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-50',  # melo by byt -100
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_products_info'

    @patch('cashier_app.transactions.make_transaction')
    @patch('cashier_app.transactions.get_pool')
    def test_successful_payment(self, mock_pool, mock_make_tx, client):
        wallet = {'id': str(uuid4()), 'owner_id': str(uuid4()), 'balance_czk': 500}
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = wallet
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        products = [{'id': str(uuid4()), 'name': 'Beer', 'price': 50, 'quantity': 2}]
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == -100

    @patch('cashier_app.transactions.get_pool')
    def test_wallet_not_found(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        products = [{'id': str(uuid4()), 'name': 'Beer', 'price': 50, 'quantity': 1}]
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-50',
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'wallet_not_found'


# ---------------------------------------------------------------------------
# make-balance-change
# ---------------------------------------------------------------------------

class TestMakeBalanceChange:

    def test_unauthenticated(self, client):
        with mock_auth(None), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-balance-change')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': 'CARD123',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_invalid_change_balance_by(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': 'CARD123',
                'change-balance-by': 'abc',
                'new-balance': '100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'change_balance_by_must_be_a_number'

    def test_invalid_new_balance(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': 'CARD123',
                'change-balance-by': '100',
                'new-balance': 'abc',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'new_balance_must_be_a_number'


# ---------------------------------------------------------------------------
# make-refund
# ---------------------------------------------------------------------------

class TestMakeRefund:

    def test_unauthenticated(self, client):
        with mock_auth(None), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-refund')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-refund')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-refund', data={
                'tag-id': 'CARD123',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_missing_tag_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-refund', data={
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'


# ---------------------------------------------------------------------------
# last-refundable
# ---------------------------------------------------------------------------

class TestGetLastRefundable:

    def test_unauthenticated(self, client):
        with mock_auth(None), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 400

    def test_missing_tag_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(SAMPLE_EVENT), mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================


def _deposit(cursor, wallet, event, booth_cashier, employee, amount):
    """Pomocná funkce pro vklad na peněženku přes přímý INSERT."""
    cursor.execute("""
        INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
            transaction_type, amount_czk, balance_before, balance_after,
            performed_by, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, 'balance-change', %s, 0, 0, %s, %s)
        RETURNING *
    """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
          event['id'], booth_cashier['id'], amount, employee['id'], str(uuid4())))
    return cursor.fetchone()


@pytest.mark.db
class TestMakePaymentDB:
    """Integrační testy make-payment s reálnou databází."""

    def test_successful_payment(self, client, db_pool, db_cursor,
                                db_wallet, db_event, db_employee_admin,
                                db_booth_cashier, db_booth_seller,
                                db_employee_role, db_employee_seller_role):
        """Vklad + platba přes API s reálnou DB."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)

        products = [{'id': str(uuid4()), 'name': 'Beer', 'price': 50, 'quantity': 2}]
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_seller), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': db_wallet['tag_id'],
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == -100

        db_cursor.execute("SELECT balance_czk FROM wallets WHERE id = %s", (db_wallet['id'],))
        assert db_cursor.fetchone()['balance_czk'] == 400

    def test_insufficient_balance(self, client, db_pool, db_cursor,
                                  db_wallet, db_event, db_employee_admin,
                                  db_booth_cashier, db_booth_seller,
                                  db_employee_role, db_employee_seller_role):
        """Platba přesahující zůstatek vrátí chybu."""
        products = [{'id': str(uuid4()), 'name': 'Expensive', 'price': 100, 'quantity': 1}]
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_seller), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': db_wallet['tag_id'],
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'wallet_balance_czk_is_not_enough'


@pytest.mark.db
class TestMakeBalanceChangeDB:
    """Integrační testy make-balance-change s reálnou DB."""

    def test_successful_deposit(self, client, db_pool, db_cursor,
                                db_wallet, db_event, db_employee_admin,
                                db_booth_cashier, db_employee_role):
        """Vklad přes API s reálnou DB."""
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_cashier), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': db_wallet['tag_id'],
                'change-balance-by': '500',
                'new-balance': '500',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == 500

        db_cursor.execute("SELECT balance_czk FROM wallets WHERE id = %s", (db_wallet['id'],))
        assert db_cursor.fetchone()['balance_czk'] == 500

    def test_withdrawal_insufficient_balance(self, client, db_pool, db_cursor,
                                             db_wallet, db_event, db_employee_admin,
                                             db_booth_cashier, db_employee_role):
        """Výběr přesahující zůstatek vrátí chybu."""
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_cashier), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': db_wallet['tag_id'],
                'change-balance-by': '-100',
                'new-balance': '-100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400


@pytest.mark.db
class TestMakeRefundDB:
    """Integrační testy make-refund s reálnou DB."""

    def test_successful_refund(self, client, db_pool, db_cursor,
                               db_wallet, db_event, db_employee_admin,
                               db_booth_cashier, db_booth_seller,
                               db_employee_role, db_employee_seller_role):
        """Vklad + platba + refund přes API."""
        # Vklad 500
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)

        # Platba 89
        products = [{'id': str(uuid4()), 'name': 'Hamburger', 'price': 89, 'quantity': 1}]
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_seller), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': db_wallet['tag_id'],
                'amount-czk': '-89',
                'idempotency-key': str(uuid4()),
                'products-info': json.dumps(products),
            })
            assert resp.status_code == 200

        # Refund
        with mock_auth_db(db_employee_admin), mock_event_db(db_event), \
             mock_booth_db(db_booth_seller), \
             patch('cashier_app.transactions.get_pool', return_value=db_pool):
            resp = client.post('/api/transactions/make-refund', data={
                'tag-id': db_wallet['tag_id'],
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['refunded_amount'] == 89
            assert data['balance_changed_by'] == 89

        db_cursor.execute("SELECT balance_czk FROM wallets WHERE id = %s", (db_wallet['id'],))
        assert db_cursor.fetchone()['balance_czk'] == 500
