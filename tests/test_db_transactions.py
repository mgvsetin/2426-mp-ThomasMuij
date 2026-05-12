"""Integrační testy transakcí a peněženek proti skutečné PostgreSQL databázi.

Testuje celé flow: deposit, payment, refund, wallet return, idempotence.
Spuštění: pytest -m db
"""

import pytest
from uuid import uuid4
from psycopg.errors import RaiseException

pytestmark = pytest.mark.db


def _deposit(cursor, wallet, event, booth_cashier, employee, amount, idemp_key=None):
    """Pomocná funkce pro vklad na peněženku."""
    cursor.execute("""
        INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
            transaction_type, amount_czk, balance_before, balance_after,
            performed_by, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, 'balance-change', %s, 0, 0, %s, %s)
        RETURNING *
    """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
          event['id'], booth_cashier['id'], amount, employee['id'],
          idemp_key or str(uuid4())))
    return cursor.fetchone()


def _payment(cursor, wallet, event, booth_seller, employee, amount, products_info='[]',
             idemp_key=None):
    """Pomocná funkce pro platbu z peněženky."""
    cursor.execute("""
        INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
            transaction_type, amount_czk, balance_before, balance_after,
            performed_by, products_info, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, 'payment', %s, 0, 0, %s, %s::jsonb, %s)
        RETURNING *
    """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
          event['id'], booth_seller['id'], amount, employee['id'],
          products_info, idemp_key or str(uuid4())))
    return cursor.fetchone()


def _refund(cursor, event, booth_seller, employee, refunded_tx_id, idemp_key=None):
    """Pomocná funkce pro refund transakce.

    Trigger automaticky nastaví tag_id, wallet_id, user_id, amount_czk, products_info
    z refundované transakce.
    """
    cursor.execute("""
        INSERT INTO transactions (event_id, booth_id,
            transaction_type, balance_before, balance_after,
            performed_by, refunded_transaction_id, idempotency_key)
        VALUES (%s, %s, 'refund', 0, 0, %s, %s, %s)
        RETURNING *
    """, (event['id'], booth_seller['id'], employee['id'],
          refunded_tx_id, idemp_key or str(uuid4())))
    return cursor.fetchone()


def _get_wallet_balance(cursor, wallet_id):
    """Získá aktuální balance_czk peněženky."""
    cursor.execute("SELECT balance_czk FROM wallets WHERE id = %s", (wallet_id,))
    return cursor.fetchone()['balance_czk']


class TestDepositAndPayment:

    def test_deposit_then_payment(self, db_cursor, db_wallet, db_event, db_employee_admin,
                                  db_booth_cashier, db_booth_seller,
                                  db_employee_role, db_employee_seller_role):
        """Vklad 500, platba 100 → zůstatek 400."""
        deposit_tx = _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        assert deposit_tx['balance_before'] == 0
        assert deposit_tx['balance_after'] == 500

        payment_tx = _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -100)
        assert payment_tx['balance_before'] == 500
        assert payment_tx['balance_after'] == 400

        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 400

    def test_multiple_transactions(self, db_cursor, db_wallet, db_event, db_employee_admin,
                                   db_booth_cashier, db_booth_seller,
                                   db_employee_role, db_employee_seller_role):
        """Série transakcí: +500, -89, -55, +200, -100 → 456."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -89)
        _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -55)
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 200)
        _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -100)

        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 456

    def test_exact_balance_payment(self, db_cursor, db_wallet, db_event, db_employee_admin,
                                   db_booth_cashier, db_booth_seller,
                                   db_employee_role, db_employee_seller_role):
        """Platba přesně celého zůstatku → 0."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 200)
        _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -200)

        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 0


class TestInsufficientBalance:

    def test_payment_exceeds_balance(self, db_conn, db_cursor, db_wallet, db_event, db_employee_admin,
                                     db_booth_cashier, db_booth_seller,
                                     db_employee_role, db_employee_seller_role):
        """Platba přesahující zůstatek vyvolá výjimku."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 100)

        # Savepoint aby transakce po chybě mohla pokračovat
        with pytest.raises(RaiseException, match="insufficient balance"):
            db_conn.execute("SAVEPOINT sp1")
            _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -200)
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")

        # Zůstatek zůstane nezměněn
        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 100

    def test_payment_on_zero_balance(self, db_conn, db_cursor, db_wallet, db_event, db_employee_admin,
                                     db_booth_seller, db_employee_seller_role):
        """Platba na prázdné peněžence vyvolá výjimku."""
        with pytest.raises(RaiseException, match="insufficient balance"):
            db_conn.execute("SAVEPOINT sp1")
            _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -1)
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")


class TestRefundFlow:

    def test_refund_restores_balance(self, db_cursor, db_wallet, db_event, db_employee_admin,
                                     db_booth_cashier, db_booth_seller,
                                     db_employee_role, db_employee_seller_role):
        """Vklad 500, platba -89, refund +89 → zůstatek 500."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        payment_tx = _payment(db_cursor, db_wallet, db_event, db_booth_seller, db_employee_admin, -89)

        refund_tx = _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                            payment_tx['id'])

        assert refund_tx['balance_before'] == 411
        assert refund_tx['balance_after'] == 500
        assert refund_tx['refunded_transaction_id'] == payment_tx['id']

        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 500

    def test_refund_auto_sets_values_from_payment(self, db_cursor, db_wallet, db_event,
                                                   db_employee_admin, db_booth_cashier,
                                                   db_booth_seller, db_employee_role,
                                                   db_employee_seller_role):
        """Trigger automaticky nastaví amount_czk, products_info, tag_id, wallet_id, user_id."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        products = '[{"id":"00000000-0000-0000-0000-000000000001","name":"Test","price":89,"quantity":1}]'
        payment_tx = _payment(db_cursor, db_wallet, db_event, db_booth_seller,
                              db_employee_admin, -89, products_info=products)

        refund_tx = _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                            payment_tx['id'])

        assert refund_tx['amount_czk'] == 89
        assert refund_tx['tag_id'] == db_wallet['tag_id']
        assert refund_tx['wallet_id'] == db_wallet['id']
        assert refund_tx['user_id'] == db_wallet['owner_id']
        assert refund_tx['products_info'] == payment_tx['products_info']

    def test_cannot_refund_non_payment(self, db_conn, db_cursor, db_wallet, db_event,
                                       db_employee_admin, db_booth_cashier, db_booth_seller,
                                       db_employee_role, db_employee_seller_role):
        """Refund balance-change transakce vyvolá výjimku."""
        deposit_tx = _deposit(db_cursor, db_wallet, db_event, db_booth_cashier,
                              db_employee_admin, 500)

        with pytest.raises(RaiseException, match="is not a payment"):
            db_conn.execute("SAVEPOINT sp1")
            _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                    deposit_tx['id'])
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")

    def test_cannot_refund_already_refunded(self, db_conn, db_cursor, db_wallet, db_event,
                                            db_employee_admin, db_booth_cashier, db_booth_seller,
                                            db_employee_role, db_employee_seller_role):
        """Dvojitý refund stejné platby vyvolá výjimku."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        payment_tx = _payment(db_cursor, db_wallet, db_event, db_booth_seller,
                              db_employee_admin, -89)

        _refund(db_cursor, db_event, db_booth_seller, db_employee_admin, payment_tx['id'])

        with pytest.raises(RaiseException, match="has already been refunded"):
            db_conn.execute("SAVEPOINT sp1")
            _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                    payment_tx['id'])
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")

    def test_refund_without_refunded_transaction_id(self, db_conn, db_cursor, db_wallet, db_event,
                                                     db_employee_admin, db_booth_cashier,
                                                     db_booth_seller, db_employee_role,
                                                     db_employee_seller_role):
        """Refund bez refunded_transaction_id vyvolá výjimku."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)

        with pytest.raises(RaiseException, match="refund must reference a transaction"):
            db_conn.execute("SAVEPOINT sp1")
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'refund', 89, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_seller['id'], db_employee_admin['id'], str(uuid4())))
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")

    def test_cannot_refund_a_refund(self, db_conn, db_cursor, db_wallet, db_event,
                                    db_employee_admin, db_booth_cashier, db_booth_seller,
                                    db_employee_role, db_employee_seller_role):
        """Refund refundu vyvolá výjimku."""
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500)
        payment_tx = _payment(db_cursor, db_wallet, db_event, db_booth_seller,
                              db_employee_admin, -89)
        refund_tx = _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                            payment_tx['id'])

        with pytest.raises(RaiseException, match="is not a payment"):
            db_conn.execute("SAVEPOINT sp1")
            _refund(db_cursor, db_event, db_booth_seller, db_employee_admin,
                    refund_tx['id'])
        db_conn.execute("ROLLBACK TO SAVEPOINT sp1")


class TestIdempotency:

    def test_duplicate_idempotency_key_ignored(self, db_cursor, db_wallet, db_event,
                                                db_employee_admin, db_booth_cashier,
                                                db_employee_role):
        """Unique index na idempotency_key zabrání duplicitnímu vložení."""
        idemp_key = str(uuid4())
        _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 500,
                 idemp_key=idemp_key)

        # Pokus o druhou transakci se stejným klíčem - vyvolá UniqueViolation
        from psycopg.errors import UniqueViolation
        db_cursor.connection.execute("SAVEPOINT sp1")
        with pytest.raises(UniqueViolation):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'balance-change', 500, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], idemp_key))
        db_cursor.connection.execute("ROLLBACK TO SAVEPOINT sp1")

        # Zůstatek je stále 500 (ne 1000)
        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 500


class TestCrossEventIsolation:

    def test_same_tag_different_events(self, db_cursor, db_employee_admin, db_user):
        """Stejný tag_id na různých eventech má nezávislé zůstatky."""
        # Vytvoř dva eventy
        db_cursor.execute("""
            INSERT INTO events (name, start_at, end_at, created_by)
            VALUES ('Event A', now() - INTERVAL '1 day', now() + INTERVAL '1 day', %s)
            RETURNING *
        """, (db_employee_admin['id'],))
        event_a = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO events (name, start_at, end_at, created_by)
            VALUES ('Event B', now() - INTERVAL '1 day', now() + INTERVAL '1 day', %s)
            RETURNING *
        """, (db_employee_admin['id'],))
        event_b = db_cursor.fetchone()

        # Vytvoř cashier stánky
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Cashier A', %s, 'cashier', %s)
            RETURNING *
        """, (event_a['id'], db_employee_admin['id']))
        booth_a = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Cashier B', %s, 'cashier', %s)
            RETURNING *
        """, (event_b['id'], db_employee_admin['id']))
        booth_b = db_cursor.fetchone()

        # Přiřaď role
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s), (%s, %s, %s)
        """, (db_employee_admin['id'], event_a['id'], booth_a['id'],
              db_employee_admin['id'], event_b['id'], booth_b['id']))

        # Vytvoř peněženky se stejným tagem
        shared_tag = 'SHARED_TAG_001'
        db_cursor.execute("""
            INSERT INTO wallets (event_id, tag_id, owner_id, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (event_a['id'], shared_tag, db_user['id'], db_employee_admin['id']))
        wallet_a = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO wallets (event_id, tag_id, owner_id, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (event_b['id'], shared_tag, db_user['id'], db_employee_admin['id']))
        wallet_b = db_cursor.fetchone()

        # Vlož na event A 500, na event B 200
        _deposit(db_cursor, wallet_a, event_a, booth_a, db_employee_admin, 500)
        _deposit(db_cursor, wallet_b, event_b, booth_b, db_employee_admin, 200)

        assert _get_wallet_balance(db_cursor, wallet_a['id']) == 500
        assert _get_wallet_balance(db_cursor, wallet_b['id']) == 200


class TestBalanceSequence:

    def test_running_balance_tracked_correctly(self, db_cursor, db_wallet, db_event,
                                                db_employee_admin, db_booth_cashier,
                                                db_employee_role):
        """Ověří, že balance_before a balance_after sedí přes sérii transakcí."""
        tx1 = _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 100)
        assert tx1['balance_before'] == 0
        assert tx1['balance_after'] == 100

        tx2 = _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, 250)
        assert tx2['balance_before'] == 100
        assert tx2['balance_after'] == 350

        tx3 = _deposit(db_cursor, db_wallet, db_event, db_booth_cashier, db_employee_admin, -50)
        assert tx3['balance_before'] == 350
        assert tx3['balance_after'] == 300

        assert _get_wallet_balance(db_cursor, db_wallet['id']) == 300
