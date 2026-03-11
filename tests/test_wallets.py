"""Testy obsluznych funkci tras modulu cashier_app.wallets."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from flask import g
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER, SAMPLE_BOOTH_SELLER,
    mock_auth, mock_auth_db, mock_booth_db,
)


def _mock_wallet_decorators(event, booth):
    """Mock pro require_booth_selected dekorátor - nastaví g.event i g.booth."""
    def _side_effect():
        g.event = event
        g.booth = booth
        return booth
    return patch('cashier_app.employee_events_booths.load_selected_booth', side_effect=_side_effect)


# ---------------------------------------------------------------------------
# POST /api/wallets/create
# ---------------------------------------------------------------------------

class TestAddWallet:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_wallet_decorators(None, None):
            resp = client.post('/api/wallets/create')
            assert resp.status_code == 401

    def test_no_booth(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(None, None):
            resp = client.post('/api/wallets/create')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/wallets/create')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_invalid_user_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/create', data={
                'user-id': 'not-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_user_id'

    def test_missing_tag_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': '',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_missing_idempotency_key(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '100',
                'new-balance': '100',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'

    def test_balance_mismatch(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '100',
                'new-balance': '200',  # neodpovida
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'change_balance_by_and_new_balance_do_not_match'

    def test_negative_new_balance(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(uuid4()),
                'tag-id': 'CARD1',
                'change-balance-by': '-50',
                'new-balance': '-50',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'wallet_balance_czk_is_not_enough'


# ---------------------------------------------------------------------------
# POST /api/wallets/return
# ---------------------------------------------------------------------------

class TestReturnWallet:

    def test_unauthenticated(self, client):
        with mock_auth(None), _mock_wallet_decorators(None, None):
            resp = client.post('/api/wallets/return')
            assert resp.status_code == 401

    def test_wrong_booth_type(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_SELLER):
            resp = client.post('/api/wallets/return')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_booth_type'

    def test_missing_tag_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/return', data={
                'tag-id': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_tag_id'

    def test_missing_idempotency_key(self, client):
        with mock_auth(ADMIN_EMPLOYEE), _mock_wallet_decorators(SAMPLE_EVENT, SAMPLE_BOOTH_CASHIER):
            resp = client.post('/api/wallets/return', data={
                'tag-id': 'CARD1',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_idempotency_key'


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
class TestAddWalletDB:
    """Integrační testy vytváření peněženky s reálnou DB."""

    def test_create_wallet_with_initial_balance(self, client, db_pool, db_cursor,
                                                db_user, db_event, db_employee_admin,
                                                db_booth_cashier, db_employee_role):
        """Vytvoření peněženky s počátečním zůstatkem přes API."""
        with mock_auth_db(db_employee_admin), \
             mock_booth_db(db_booth_cashier, db_event), \
             patch('cashier_app.wallets.get_pool', return_value=db_pool):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(db_user['id']),
                'tag-id': 'NEW_TAG_001',
                'change-balance-by': '300',
                'new-balance': '300',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == 300

        db_cursor.execute("""
            SELECT balance_czk FROM wallets
            WHERE tag_id = 'NEW_TAG_001' AND event_id = %s AND deleted_at IS NULL
        """, (db_event['id'],))
        assert db_cursor.fetchone()['balance_czk'] == 300

    def test_create_wallet_zero_balance(self, client, db_pool, db_cursor,
                                        db_user, db_event, db_employee_admin,
                                        db_booth_cashier, db_employee_role):
        """Vytvoření peněženky s nulovým zůstatkem."""
        with mock_auth_db(db_employee_admin), \
             mock_booth_db(db_booth_cashier, db_event), \
             patch('cashier_app.wallets.get_pool', return_value=db_pool):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(db_user['id']),
                'tag-id': 'ZERO_TAG_001',
                'change-balance-by': '0',
                'new-balance': '0',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT balance_czk FROM wallets
            WHERE tag_id = 'ZERO_TAG_001' AND event_id = %s AND deleted_at IS NULL
        """, (db_event['id'],))
        assert db_cursor.fetchone()['balance_czk'] == 0

    def test_duplicate_tag_id_rejected(self, client, db_pool, db_cursor,
                                       db_wallet, db_event, db_employee_admin,
                                       db_booth_cashier, db_employee_role):
        """Duplicitní tag_id na stejném eventu vrátí chybu."""
        with mock_auth_db(db_employee_admin), \
             mock_booth_db(db_booth_cashier, db_event), \
             patch('cashier_app.wallets.get_pool', return_value=db_pool):
            resp = client.post('/api/wallets/create', data={
                'user-id': str(db_wallet['owner_id']),
                'tag-id': db_wallet['tag_id'],
                'change-balance-by': '100',
                'new-balance': '100',
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'tag_id_taken'


@pytest.mark.db
class TestReturnWalletDB:
    """Integrační testy vrácení peněženky s reálnou DB."""

    def test_return_wallet_with_balance(self, client, db_pool, db_cursor,
                                       db_wallet, db_event, db_employee_admin,
                                       db_booth_cashier, db_employee_role):
        """Vrácení peněženky se zůstatkem: vynuluje a soft-deletne."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 250)

        with mock_auth_db(db_employee_admin), \
             mock_booth_db(db_booth_cashier, db_event), \
             patch('cashier_app.wallets.get_pool', return_value=db_pool):
            resp = client.post('/api/wallets/return', data={
                'tag-id': db_wallet['tag_id'],
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == -250

        db_cursor.execute("SELECT balance_czk, deleted_at FROM wallets WHERE id = %s",
                          (db_wallet['id'],))
        wallet = db_cursor.fetchone()
        assert wallet['balance_czk'] == 0
        assert wallet['deleted_at'] is not None

    def test_return_wallet_zero_balance(self, client, db_pool, db_cursor,
                                       db_wallet, db_event, db_employee_admin,
                                       db_booth_cashier, db_employee_role):
        """Vrácení peněženky s nulovým zůstatkem."""
        with mock_auth_db(db_employee_admin), \
             mock_booth_db(db_booth_cashier, db_event), \
             patch('cashier_app.wallets.get_pool', return_value=db_pool):
            resp = client.post('/api/wallets/return', data={
                'tag-id': db_wallet['tag_id'],
                'idempotency-key': str(uuid4()),
            })
            assert resp.status_code == 200
            assert resp.get_json()['balance_changed_by'] == 0
