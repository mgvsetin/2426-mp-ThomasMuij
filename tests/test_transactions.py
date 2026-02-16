"""Testy obsluznych funkci tras modulu cashier_app.transactions."""

import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    set_session, ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    SAMPLE_EVENT, SAMPLE_BOOTH_SELLER, SAMPLE_BOOTH_CASHIER,
)


def _mock_auth(employee):
    """Vrati patch pro load_logged_in_employee."""
    return patch('cashier_app.transactions.load_logged_in_employee', return_value=employee)


def _mock_event(event):
    return patch('cashier_app.transactions.load_selected_event', return_value=event)


def _mock_booth(booth):
    return patch('cashier_app.transactions.load_selected_booth', return_value=booth)


# ---------------------------------------------------------------------------
# make-payment
# ---------------------------------------------------------------------------

class TestMakePayment:

    def test_unauthenticated(self, client):
        with _mock_auth(None), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 401

    def test_no_selected_event(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(None), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_no_selected_booth(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(None):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-payment')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-100',
                'products-info': '[]',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_missing_tag_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': '',
                'amount-czk': '-100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_invalid_amount(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': 'abc',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'amount_czk_must_be_a_number'

    def test_non_integer_amount(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '10.5',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'amount_czk_must_be_a_whole_number'

    def test_amount_too_low(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '-1000001',
                'idempotency-key': str(uuid4()),
                'products-info': '[]',
            })
            assert resp.status_code == 400

    def test_amount_too_high(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-payment', data={
                'tag-id': 'CARD123',
                'amount-czk': '1000001',
                'idempotency-key': str(uuid4()),
                'products-info': '[]',
            })
            assert resp.status_code == 400

    def test_invalid_products_info_json(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
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
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
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
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
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
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
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
        with _mock_auth(None), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-balance-change')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': 'CARD123',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_invalid_change_balance_by(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-balance-change', data={
                'tag-id': 'CARD123',
                'change-balance-by': 'abc',
                'new-balance': '100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'change_balance_by_must_be_a_number'

    def test_invalid_new_balance(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
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
        with _mock_auth(None), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-refund')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/transactions/make-refund')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_idempotency_key(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/transactions/make-refund', data={
                'tag-id': 'CARD123',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_missing_tag_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
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
        with _mock_auth(None), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_CASHIER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 400

    def test_missing_tag_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), _mock_event(SAMPLE_EVENT), _mock_booth(SAMPLE_BOOTH_SELLER):
            resp = client.get('/api/transactions/last-refundable')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'
