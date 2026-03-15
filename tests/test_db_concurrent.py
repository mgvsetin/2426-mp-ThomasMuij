"""Testy souběžných (concurrent) transakcí proti skutečné PostgreSQL databázi.

Ověřují, že PostgreSQL zámky (FOR UPDATE) v triggerech správně
serializují souběžné operace a nedojde k race conditions.

Spuštění: pytest -m db -k concurrent
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest
from psycopg.rows import dict_row

from tests.conftest import DB_TEST_CONNINFO, FAKE_HASH

pytestmark = pytest.mark.db


# ---------------------------------------------------------------------------
# Fixtures — concurrent testy potřebují COMMIT (více spojení musí vidět data)
# ---------------------------------------------------------------------------

@pytest.fixture()
def committed_data(_db_pool):
    """Vloží testovací data a commitne je, aby je viděly všechna spojení.

    Po testu data uklidí.
    """
    with _db_pool.connection() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            # employee
            cur.execute("""
                INSERT INTO employees (username, email, password_hash, is_admin)
                VALUES (%s, %s, %s, TRUE)
                RETURNING *
            """, (f'concurrent_admin_{uuid4().hex[:8]}',
                  f'concurrent_{uuid4().hex[:8]}@test.com', FAKE_HASH))
            employee = cur.fetchone()

            # event
            cur.execute("""
                INSERT INTO events (name, start_at, end_at, created_by)
                VALUES (%s, now() - INTERVAL '1 day', now() + INTERVAL '1 day', %s)
                RETURNING *
            """, (f'Concurrent Event {uuid4().hex[:8]}', employee['id']))
            event = cur.fetchone()

            # cashier booth
            cur.execute("""
                INSERT INTO booths (name, event_id, booth_type, created_by)
                VALUES ('Concurrent Cashier', %s, 'cashier', %s)
                RETURNING *
            """, (event['id'], employee['id']))
            booth_cashier = cur.fetchone()

            # seller booth
            cur.execute("""
                INSERT INTO booths (name, event_id, booth_type, created_by)
                VALUES ('Concurrent Seller', %s, 'seller', %s)
                RETURNING *
            """, (event['id'], employee['id']))
            booth_seller = cur.fetchone()

            # user
            cur.execute("""
                INSERT INTO users (first_name, last_name, email)
                VALUES ('Concurrent', 'User', %s)
                RETURNING *
            """, (f'concurrent_{uuid4().hex[:8]}@test.com',))
            user = cur.fetchone()

            # role assignments
            cur.execute("""
                INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
                VALUES (%s, %s, %s), (%s, %s, %s)
            """, (employee['id'], event['id'], booth_cashier['id'],
                  employee['id'], event['id'], booth_seller['id']))

            # wallet
            cur.execute("""
                INSERT INTO wallets (event_id, tag_id, owner_id, created_by)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (event['id'], f'CONC_TAG_{uuid4().hex[:8]}', user['id'], employee['id']))
            wallet = cur.fetchone()

        conn.commit()

    data = {
        'employee': employee,
        'event': event,
        'booth_cashier': booth_cashier,
        'booth_seller': booth_seller,
        'user': user,
        'wallet': wallet,
    }

    yield data

    # Cleanup — trigger blokuje DELETE na transactions, je třeba ho dočasně vypnout
    with _db_pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE transactions DISABLE TRIGGER trg_transactions_block_delete_update_limit_insert")
            cur.execute("DELETE FROM transactions WHERE wallet_id = %s", (wallet['id'],))
            cur.execute("ALTER TABLE transactions ENABLE TRIGGER trg_transactions_block_delete_update_limit_insert")
            cur.execute("DELETE FROM wallets WHERE id = %s", (wallet['id'],))
            cur.execute("DELETE FROM employee_event_booth_roles WHERE employee_id = %s",
                        (employee['id'],))
            cur.execute("DELETE FROM booths WHERE event_id = %s", (event['id'],))
            cur.execute("DELETE FROM events WHERE id = %s", (event['id'],))
            cur.execute("DELETE FROM users WHERE id = %s", (user['id'],))
            cur.execute("DELETE FROM employees WHERE id = %s", (employee['id'],))


def _new_conn():
    """Vytvoří nové nezávislé připojení k testovací DB."""
    import psycopg
    conn = psycopg.connect(DB_TEST_CONNINFO, row_factory=dict_row)
    conn.autocommit = False
    return conn


def _deposit_on_conn(conn, wallet, event, booth_cashier, employee, amount):
    """Provede vklad na vlastním spojení a commitne."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'balance-change', %s, 0, 0, %s, %s)
            RETURNING *
        """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
              event['id'], booth_cashier['id'], amount, employee['id'], str(uuid4())))
        result = cur.fetchone()
    conn.commit()
    return result


def _payment_on_conn(conn, wallet, event, booth_seller, employee, amount):
    """Provede platbu na vlastním spojení a commitne."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, products_info, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'payment', %s, 0, 0, %s, '[]'::jsonb, %s)
            RETURNING *
        """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
              event['id'], booth_seller['id'], amount, employee['id'], str(uuid4())))
        result = cur.fetchone()
    conn.commit()
    return result


def _refund_on_conn(conn, event, booth_seller, employee, refunded_tx_id):
    """Provede refund na vlastním spojení a commitne."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO transactions (event_id, booth_id,
                transaction_type, balance_before, balance_after,
                performed_by, refunded_transaction_id, idempotency_key)
            VALUES (%s, %s, 'refund', 0, 0, %s, %s, %s)
            RETURNING *
        """, (event['id'], booth_seller['id'], employee['id'],
              refunded_tx_id, str(uuid4())))
        result = cur.fetchone()
    conn.commit()
    return result


def _get_balance(conn, wallet_id):
    """Získá aktuální balance peněženky."""
    with conn.cursor() as cur:
        cur.execute("SELECT balance_czk FROM wallets WHERE id = %s", (wallet_id,))
        return cur.fetchone()['balance_czk']


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------

class TestConcurrentDeposits:
    """Souběžné vklady na stejnou peněženku."""

    def test_two_concurrent_deposits(self, committed_data):
        """Dva vlákna současně vloží peníze — výsledný zůstatek musí být součet obou."""
        d = committed_data
        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_deposit(amount):
            conn = _new_conn()
            try:
                barrier.wait()
                tx = _deposit_on_conn(conn, d['wallet'], d['event'],
                                      d['booth_cashier'], d['employee'], amount)
                results.append(('ok', tx))
            except Exception as e:
                conn.rollback()
                results.append(('error', e))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_deposit, 300), pool.submit(do_deposit, 200)]
            for f in as_completed(futures):
                f.result()

        # Oba vklady musí uspět
        assert all(r[0] == 'ok' for r in results), f"Unexpected errors: {results}"

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 500, f"Expected 500, got {balance}"
        finally:
            conn.close()

    def test_many_concurrent_deposits(self, committed_data):
        """5 vláken současně vloží po 100 Kč — výsledný zůstatek musí být 500."""
        d = committed_data
        num_threads = 5
        barrier = threading.Barrier(num_threads, timeout=5)
        errors = []

        def do_deposit():
            conn = _new_conn()
            try:
                barrier.wait()
                _deposit_on_conn(conn, d['wallet'], d['event'],
                                 d['booth_cashier'], d['employee'], 100)
            except Exception as e:
                conn.rollback()
                errors.append(e)
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            futures = [pool.submit(do_deposit) for _ in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        assert not errors, f"Unexpected errors: {errors}"

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 500, f"Expected 500, got {balance}"
        finally:
            conn.close()


class TestConcurrentPayments:
    """Souběžné platby ze stejné peněženky."""

    def test_two_concurrent_payments_sufficient_balance(self, committed_data):
        """Dvě platby, obě by měly projít — zůstatek = deposit - obě platby."""
        d = committed_data

        # Nejdřív vklad
        conn = _new_conn()
        _deposit_on_conn(conn, d['wallet'], d['event'],
                         d['booth_cashier'], d['employee'], 500)
        conn.close()

        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_payment(amount):
            conn = _new_conn()
            try:
                barrier.wait()
                tx = _payment_on_conn(conn, d['wallet'], d['event'],
                                      d['booth_seller'], d['employee'], amount)
                results.append(('ok', tx))
            except Exception as e:
                conn.rollback()
                results.append(('error', e))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_payment, -100), pool.submit(do_payment, -150)]
            for f in as_completed(futures):
                f.result()

        assert all(r[0] == 'ok' for r in results), f"Unexpected errors: {results}"

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 250, f"Expected 250, got {balance}"
        finally:
            conn.close()

    def test_concurrent_payments_one_exceeds_balance(self, committed_data):
        """Vklad 200, dvě platby po -150 — jen jedna projde, druhá selže na insufficient balance."""
        d = committed_data

        conn = _new_conn()
        _deposit_on_conn(conn, d['wallet'], d['event'],
                         d['booth_cashier'], d['employee'], 200)
        conn.close()

        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_payment():
            conn = _new_conn()
            try:
                barrier.wait()
                tx = _payment_on_conn(conn, d['wallet'], d['event'],
                                      d['booth_seller'], d['employee'], -150)
                results.append(('ok', tx))
            except Exception as e:
                conn.rollback()
                results.append(('error', str(e)))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_payment) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        ok_count = sum(1 for r in results if r[0] == 'ok')
        err_count = sum(1 for r in results if r[0] == 'error')
        assert ok_count == 1, f"Expected exactly 1 success, got {ok_count}: {results}"
        assert err_count == 1, f"Expected exactly 1 error, got {err_count}: {results}"
        assert any('insufficient balance' in r[1] for r in results if r[0] == 'error')

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 50, f"Expected 50, got {balance}"
        finally:
            conn.close()


class TestConcurrentRefunds:
    """Souběžné refundy stejné platby."""

    def test_double_refund_race(self, committed_data):
        """Dvě vlákna současně refundují stejnou platbu — jen jeden refund projde."""
        d = committed_data

        conn = _new_conn()
        _deposit_on_conn(conn, d['wallet'], d['event'],
                         d['booth_cashier'], d['employee'], 500)
        payment_tx = _payment_on_conn(conn, d['wallet'], d['event'],
                                      d['booth_seller'], d['employee'], -200)
        conn.close()

        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_refund():
            conn = _new_conn()
            try:
                barrier.wait()
                tx = _refund_on_conn(conn, d['event'], d['booth_seller'],
                                     d['employee'], payment_tx['id'])
                results.append(('ok', tx))
            except Exception as e:
                conn.rollback()
                results.append(('error', str(e)))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_refund) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        ok_count = sum(1 for r in results if r[0] == 'ok')
        err_count = sum(1 for r in results if r[0] == 'error')
        assert ok_count == 1, f"Expected exactly 1 successful refund, got {ok_count}: {results}"
        assert err_count == 1, f"Expected exactly 1 failed refund, got {err_count}: {results}"
        assert any('has already been refunded' in r[1] for r in results if r[0] == 'error')

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 500, f"Expected 500 after refund, got {balance}"
        finally:
            conn.close()


class TestConcurrentDepositAndPayment:
    """Souběžný vklad a platba na stejné peněžence."""

    def test_deposit_and_payment_concurrent(self, committed_data):
        """Vklad +300 a platba -100 současně na peněženku s 200 Kč — zůstatek musí být 400."""
        d = committed_data

        conn = _new_conn()
        _deposit_on_conn(conn, d['wallet'], d['event'],
                         d['booth_cashier'], d['employee'], 200)
        conn.close()

        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_deposit():
            conn = _new_conn()
            try:
                barrier.wait()
                _deposit_on_conn(conn, d['wallet'], d['event'],
                                 d['booth_cashier'], d['employee'], 300)
                results.append(('ok', 'deposit'))
            except Exception as e:
                conn.rollback()
                results.append(('error', str(e)))
            finally:
                conn.close()

        def do_payment():
            conn = _new_conn()
            try:
                barrier.wait()
                _payment_on_conn(conn, d['wallet'], d['event'],
                                 d['booth_seller'], d['employee'], -100)
                results.append(('ok', 'payment'))
            except Exception as e:
                conn.rollback()
                results.append(('error', str(e)))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_deposit), pool.submit(do_payment)]
            for f in as_completed(futures):
                f.result()

        assert all(r[0] == 'ok' for r in results), f"Unexpected errors: {results}"

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 400, f"Expected 400, got {balance}"
        finally:
            conn.close()


class TestConcurrentIdempotency:
    """Souběžné vložení se stejným idempotency_key."""

    def test_duplicate_idempotency_key_concurrent(self, committed_data):
        """Dvě vlákna současně vloží transakci se stejným idempotency_key — jen jedna projde."""
        d = committed_data
        idemp_key = str(uuid4())
        barrier = threading.Barrier(2, timeout=5)
        results = []

        def do_deposit():
            conn = _new_conn()
            try:
                barrier.wait()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                            transaction_type, amount_czk, balance_before, balance_after,
                            performed_by, idempotency_key)
                        VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
                        RETURNING *
                    """, (d['wallet']['tag_id'], d['wallet']['id'], d['wallet']['owner_id'],
                          d['event']['id'], d['booth_cashier']['id'], d['employee']['id'],
                          idemp_key))
                    cur.fetchone()
                conn.commit()
                results.append(('ok',))
            except Exception as e:
                conn.rollback()
                results.append(('error', str(e)))
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_deposit) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        ok_count = sum(1 for r in results if r[0] == 'ok')
        err_count = sum(1 for r in results if r[0] == 'error')
        assert ok_count == 1, f"Expected exactly 1 success, got {ok_count}: {results}"
        assert err_count == 1, f"Expected exactly 1 error, got {err_count}: {results}"

        conn = _new_conn()
        try:
            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == 100, f"Expected 100, got {balance}"
        finally:
            conn.close()


class TestConcurrentBalanceConsistency:
    """Ověřuje konzistenci balance_before/balance_after při souběžných operacích."""

    def test_balance_chain_consistent_after_concurrent_ops(self, committed_data):
        """Po sérii souběžných vkladů musí balance_before/balance_after tvořit nepřerušený řetěz."""
        d = committed_data
        num_threads = 4
        barrier = threading.Barrier(num_threads, timeout=5)
        errors = []

        def do_deposit():
            conn = _new_conn()
            try:
                barrier.wait()
                _deposit_on_conn(conn, d['wallet'], d['event'],
                                 d['booth_cashier'], d['employee'], 100)
            except Exception as e:
                conn.rollback()
                errors.append(e)
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            futures = [pool.submit(do_deposit) for _ in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        assert not errors, f"Unexpected errors: {errors}"

        # Ověř, že balance_before/after tvoří řetěz
        conn = _new_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT balance_before, balance_after
                    FROM transactions
                    WHERE wallet_id = %s
                    ORDER BY balance_before
                """, (d['wallet']['id'],))
                txs = cur.fetchall()

            assert len(txs) == num_threads

            # Každá transakce: balance_after předchozí == balance_before této
            for i in range(1, len(txs)):
                assert txs[i]['balance_before'] == txs[i - 1]['balance_after'], \
                    f"Break in balance chain at tx {i}: prev.after={txs[i-1]['balance_after']}, " \
                    f"curr.before={txs[i]['balance_before']}"

            # Finální balance
            assert txs[-1]['balance_after'] == num_threads * 100

            balance = _get_balance(conn, d['wallet']['id'])
            assert balance == num_threads * 100
        finally:
            conn.close()
