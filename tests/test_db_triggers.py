"""Integrační testy databázových triggerů proti skutečné PostgreSQL databázi.

Spuštění: pytest -m db
Vyžaduje běžící PostgreSQL s databází cashier_app_test.
"""

import pytest
from uuid import uuid4
from psycopg.errors import RaiseException

pytestmark = pytest.mark.db


# ======================== employees trigger ========================

class TestEmployeesTrigger:

    def test_soft_delete(self, db_cursor, db_employee_admin):
        """DELETE na employees provede soft-delete (nastaví deleted_at)."""
        db_cursor.execute("DELETE FROM employees WHERE id = %s", (db_employee_admin['id'],))
        db_cursor.execute("SELECT deleted_at FROM employees WHERE id = %s", (db_employee_admin['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_immutable_created_at(self, db_cursor, db_employee_admin):
        """Změna created_at vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_at is immutable"):
            db_cursor.execute(
                "UPDATE employees SET created_at = now() - INTERVAL '1 year' WHERE id = %s",
                (db_employee_admin['id'],))

    def test_immutable_created_by(self, db_cursor, db_employee_admin):
        """Změna created_by vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_by is immutable"):
            db_cursor.execute(
                "UPDATE employees SET created_by = %s WHERE id = %s",
                (db_employee_admin['id'], db_employee_admin['id']))

    def test_whitespace_trimming(self, db_cursor, db_employee_admin):
        """Trigger odstraní mezery z username a email, email dá malým."""
        db_cursor.execute("""
            INSERT INTO employees (username, email, password_hash, is_admin, created_by)
            VALUES ('  trimmed_user  ', '  UPPER@EXAMPLE.COM  ',
                    '$argon2id$v=19$m=1024,t=1,p=1$dGVzdHNhbHQ$dGVzdGhhc2g', FALSE, %s)
            RETURNING username, email
        """, (db_employee_admin['id'],))
        row = db_cursor.fetchone()
        assert row['username'] == 'trimmed_user'
        assert row['email'] == 'upper@example.com'


# ======================== users trigger ========================

class TestUsersTrigger:

    def test_soft_delete(self, db_cursor, db_user):
        """DELETE na users provede soft-delete."""
        db_cursor.execute("DELETE FROM users WHERE id = %s", (db_user['id'],))
        db_cursor.execute("SELECT deleted_at FROM users WHERE id = %s", (db_user['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_cascade_delete_wallets(self, db_cursor, db_wallet, db_user):
        """Soft-delete uživatele kaskádově soft-deletne jeho peněženky."""
        db_cursor.execute("DELETE FROM users WHERE id = %s", (db_user['id'],))
        db_cursor.execute("SELECT deleted_at FROM wallets WHERE id = %s", (db_wallet['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_name_capitalization(self, db_cursor):
        """Trigger dá první písmeno jména a příjmení velké."""
        db_cursor.execute("""
            INSERT INTO users (first_name, last_name, email)
            VALUES ('oNdŘej', 'procházka', 'ondřej.procházka@example.com')
            RETURNING first_name, last_name
        """)
        row = db_cursor.fetchone()
        assert row['first_name'] == 'Ondřej'
        assert row['last_name'] == 'Procházka'

    def test_email_lowercased(self, db_cursor):
        """Trigger převede email na malá písmena."""
        db_cursor.execute("""
            INSERT INTO users (first_name, last_name, email)
            VALUES ('Jane', 'Doe', 'JANE.DOE@EXAMPLE.COM')
            RETURNING email
        """)
        row = db_cursor.fetchone()
        assert row['email'] == 'jane.doe@example.com'

    def test_at_least_one_identifier_required(self, db_cursor):
        """Bez email, phone_number nebo other_identifier vyvolá výjimku."""
        with pytest.raises(RaiseException, match="at least one of"):
            db_cursor.execute("""
                INSERT INTO users (first_name, last_name)
                VALUES ('No', 'Identifier')
            """)

    def test_immutable_created_at(self, db_cursor, db_user):
        """Změna created_at vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_at is immutable"):
            db_cursor.execute(
                "UPDATE users SET created_at = now() - INTERVAL '1 year' WHERE id = %s",
                (db_user['id'],))

    def test_whitespace_trimming(self, db_cursor):
        """Trigger odstraní přebytečné mezery ze jmen a emailu."""
        db_cursor.execute("""
            INSERT INTO users (first_name, last_name, email)
            VALUES ('  alice  ', '  smith  ', '  alice@example.com  ')
            RETURNING first_name, last_name, email
        """)
        row = db_cursor.fetchone()
        assert row['first_name'] == 'Alice'
        assert row['last_name'] == 'Smith'
        assert row['email'] == 'alice@example.com'


# ======================== events trigger ========================

class TestEventsTrigger:

    def test_soft_delete(self, db_cursor, db_event):
        """DELETE na events provede soft-delete."""
        db_cursor.execute("DELETE FROM events WHERE id = %s", (db_event['id'],))
        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s", (db_event['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_immutable_created_at(self, db_cursor, db_event):
        """Změna created_at vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_at is immutable"):
            db_cursor.execute(
                "UPDATE events SET created_at = now() - INTERVAL '1 year' WHERE id = %s",
                (db_event['id'],))

    def test_immutable_created_by(self, db_cursor, db_event):
        """Změna created_by vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_by is immutable"):
            db_cursor.execute(
                "UPDATE events SET created_by = gen_random_uuid() WHERE id = %s",
                (db_event['id'],))

    def test_name_trimming(self, db_cursor, db_employee_admin):
        """Trigger odstraní mezery z názvu akce."""
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('  Trimmed Event  ', now(), %s)
            RETURNING name
        """, (db_employee_admin['id'],))
        row = db_cursor.fetchone()
        assert row['name'] == 'Trimmed Event'


# ======================== booths trigger ========================

class TestBoothsTrigger:

    def test_soft_delete(self, db_cursor, db_booth_cashier):
        """DELETE na booths provede soft-delete."""
        db_cursor.execute("DELETE FROM booths WHERE id = %s", (db_booth_cashier['id'],))
        db_cursor.execute("SELECT deleted_at FROM booths WHERE id = %s", (db_booth_cashier['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_immutable_event_id(self, db_cursor, db_booth_cashier):
        """Změna event_id vyvolá výjimku."""
        with pytest.raises(RaiseException, match="event_id is immutable"):
            db_cursor.execute(
                "UPDATE booths SET event_id = gen_random_uuid() WHERE id = %s",
                (db_booth_cashier['id'],))

    def test_immutable_booth_type(self, db_cursor, db_booth_cashier):
        """Změna booth_type vyvolá výjimku."""
        with pytest.raises(RaiseException, match="booth_type is immutable"):
            db_cursor.execute(
                "UPDATE booths SET booth_type = 'seller' WHERE id = %s",
                (db_booth_cashier['id'],))

    def test_immutable_created_at(self, db_cursor, db_booth_cashier):
        """Změna created_at vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_at is immutable"):
            db_cursor.execute(
                "UPDATE booths SET created_at = now() - INTERVAL '1 year' WHERE id = %s",
                (db_booth_cashier['id'],))

    def test_immutable_created_by(self, db_cursor, db_booth_cashier):
        """Změna created_by vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_by is immutable"):
            db_cursor.execute(
                "UPDATE booths SET created_by = gen_random_uuid() WHERE id = %s",
                (db_booth_cashier['id'],))

    def test_name_trimming(self, db_cursor, db_event, db_employee_admin):
        """Trigger odstraní mezery z názvu stánku."""
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('  Trimmed Booth  ', %s, 'seller', %s)
            RETURNING name
        """, (db_event['id'], db_employee_admin['id']))
        row = db_cursor.fetchone()
        assert row['name'] == 'Trimmed Booth'


# ======================== wallets trigger ========================

class TestWalletsTrigger:

    def test_soft_delete(self, db_cursor, db_wallet):
        """DELETE na wallets provede soft-delete."""
        db_cursor.execute("DELETE FROM wallets WHERE id = %s", (db_wallet['id'],))
        db_cursor.execute("SELECT deleted_at FROM wallets WHERE id = %s", (db_wallet['id'],))
        row = db_cursor.fetchone()
        assert row['deleted_at'] is not None

    def test_immutable_created_at(self, db_cursor, db_wallet):
        """Změna created_at vyvolá výjimku."""
        with pytest.raises(RaiseException, match="created_at is immutable"):
            db_cursor.execute(
                "UPDATE wallets SET created_at = now() - INTERVAL '1 year' WHERE id = %s",
                (db_wallet['id'],))

    def test_initial_balance_zero(self, db_cursor, db_wallet):
        """Nová peněženka má balance_czk = 0."""
        assert db_wallet['balance_czk'] == 0


# ======================== transactions trigger ========================

class TestTransactionsTrigger:

    def test_block_update(self, db_cursor, db_wallet, db_employee_admin, db_event,
                          db_booth_cashier, db_employee_role):
        """UPDATE na transactions vyvolá výjimku."""
        db_cursor.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            RETURNING id
        """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
              db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))
        tx = db_cursor.fetchone()

        with pytest.raises(RaiseException, match="Updates are not allowed"):
            db_cursor.execute(
                "UPDATE transactions SET amount_czk = 200 WHERE id = %s", (tx['id'],))

    def test_block_delete(self, db_cursor, db_wallet, db_employee_admin, db_event,
                          db_booth_cashier, db_employee_role):
        """DELETE na transactions vyvolá výjimku."""
        db_cursor.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            RETURNING id
        """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
              db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))
        tx = db_cursor.fetchone()

        with pytest.raises(RaiseException, match="Deletes are not allowed"):
            db_cursor.execute("DELETE FROM transactions WHERE id = %s", (tx['id'],))

    def test_balance_calculation(self, db_cursor, db_wallet, db_employee_admin, db_event,
                                 db_booth_cashier, db_employee_role):
        """Trigger vypočítá balance_before a balance_after."""
        db_cursor.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'balance-change', 500, 0, 0, %s, %s)
            RETURNING balance_before, balance_after
        """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
              db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))
        tx = db_cursor.fetchone()
        assert tx['balance_before'] == 0
        assert tx['balance_after'] == 500

    def test_wallet_balance_cache_updated(self, db_cursor, db_wallet, db_employee_admin,
                                          db_event, db_booth_cashier, db_employee_role):
        """Trigger aktualizuje wallet.balance_czk po vložení transakce."""
        db_cursor.execute("""
            INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                transaction_type, amount_czk, balance_before, balance_after,
                performed_by, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, 'balance-change', 300, 0, 0, %s, %s)
        """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
              db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))

        db_cursor.execute("SELECT balance_czk FROM wallets WHERE id = %s", (db_wallet['id'],))
        wallet = db_cursor.fetchone()
        assert wallet['balance_czk'] == 300

    def test_insufficient_balance(self, db_cursor, db_wallet, db_employee_admin, db_event,
                                  db_booth_seller, db_employee_seller_role):
        """Transakce, která by způsobila záporný zůstatek, vyvolá výjimku."""
        with pytest.raises(RaiseException, match="insufficient balance"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'payment', -100, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_seller['id'], db_employee_admin['id'], str(uuid4())))

    def test_inactive_event_rejected(self, db_cursor, db_employee_admin, db_user):
        """Transakce na neaktivní event vyvolá výjimku."""
        # Vytvoř event v budoucnosti
        db_cursor.execute("""
            INSERT INTO events (name, start_at, end_at, created_by)
            VALUES ('Future Event', now() + INTERVAL '1 day', now() + INTERVAL '2 days', %s)
            RETURNING *
        """, (db_employee_admin['id'],))
        future_event = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Booth', %s, 'cashier', %s)
            RETURNING *
        """, (future_event['id'], db_employee_admin['id']))
        booth = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO wallets (event_id, tag_id, owner_id, created_by)
            VALUES (%s, 'FUTURE_TAG', %s, %s)
            RETURNING *
        """, (future_event['id'], db_user['id'], db_employee_admin['id']))
        wallet = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
        """, (db_employee_admin['id'], future_event['id'], booth['id']))

        with pytest.raises(RaiseException, match="is not active"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            """, (wallet['tag_id'], wallet['id'], wallet['owner_id'],
                  future_event['id'], booth['id'], db_employee_admin['id'], str(uuid4())))

    def test_booth_type_cashier_rejects_payment(self, db_cursor, db_wallet, db_employee_admin,
                                                 db_event, db_booth_cashier, db_employee_role):
        """Cashier stánek nemůže provést payment."""
        with pytest.raises(RaiseException, match="invalid booth type"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'payment', -50, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))

    def test_booth_type_seller_rejects_balance_change(self, db_cursor, db_wallet, db_employee_admin,
                                                       db_event, db_booth_seller,
                                                       db_employee_seller_role):
        """Seller stánek nemůže provést balance-change."""
        with pytest.raises(RaiseException, match="invalid booth type"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_seller['id'], db_employee_admin['id'], str(uuid4())))

    def test_wallet_tag_mismatch_rejected(self, db_cursor, db_wallet, db_employee_admin,
                                          db_event, db_booth_cashier, db_employee_role):
        """Transakce s nesprávným tag_id vyvolá výjimku."""
        with pytest.raises(RaiseException, match="tag_id.*does not match"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES ('WRONG_TAG', %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            """, (db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_cashier['id'], db_employee_admin['id'], str(uuid4())))

    def test_employee_without_role_rejected(self, db_cursor, db_wallet, db_event,
                                            db_booth_cashier, db_employee_admin):
        """Zaměstnanec bez role (a bez admin) nemůže provést transakci."""
        # Vytvoř non-admin zaměstnance bez role
        db_cursor.execute("""
            INSERT INTO employees (username, email, password_hash, is_admin, created_by)
            VALUES ('norole', 'norole@example.com',
                    '$argon2id$v=19$m=1024,t=1,p=1$dGVzdHNhbHQ$dGVzdGhhc2g', FALSE, %s)
            RETURNING *
        """, (db_employee_admin['id'],))
        no_role_emp = db_cursor.fetchone()

        with pytest.raises(RaiseException, match="does not have any role"):
            db_cursor.execute("""
                INSERT INTO transactions (tag_id, wallet_id, user_id, event_id, booth_id,
                    transaction_type, amount_czk, balance_before, balance_after,
                    performed_by, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'balance-change', 100, 0, 0, %s, %s)
            """, (db_wallet['tag_id'], db_wallet['id'], db_wallet['owner_id'],
                  db_event['id'], db_booth_cashier['id'], no_role_emp['id'], str(uuid4())))


# ======================== employee_event_booth_roles trigger ========================

class TestEmployeeEventBoothRolesTrigger:

    def test_auto_complete_role_cashier(self, db_cursor, db_employee_regular, db_event,
                                        db_booth_cashier):
        """Trigger automaticky doplní roli 'cashier' podle booth_type."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
            RETURNING role
        """, (db_employee_regular['id'], db_event['id'], db_booth_cashier['id']))
        row = db_cursor.fetchone()
        assert row['role'] == 'cashier'

    def test_auto_complete_role_seller(self, db_cursor, db_employee_regular, db_event,
                                       db_booth_seller):
        """Trigger automaticky doplní roli 'seller' podle booth_type."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
            RETURNING role
        """, (db_employee_regular['id'], db_event['id'], db_booth_seller['id']))
        row = db_cursor.fetchone()
        assert row['role'] == 'seller'

    def test_auto_complete_event_manager(self, db_cursor, db_employee_regular, db_event):
        """Trigger automaticky doplní roli 'event_manager' když booth_id je NULL."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id, role)
            VALUES (%s, %s, NULL, NULL)
            RETURNING role
        """, (db_employee_regular['id'], db_event['id']))
        row = db_cursor.fetchone()
        assert row['role'] == 'event_manager'

    def test_event_manager_cannot_be_assigned_to_booth(self, db_cursor, db_employee_regular,
                                                        db_event, db_booth_cashier):
        """Zaměstnanec, který je event_manager, nemůže být přiřazen ke stánku."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id, role)
            VALUES (%s, %s, NULL, 'event_manager')
        """, (db_employee_regular['id'], db_event['id']))

        with pytest.raises(RaiseException, match="already event_manager"):
            db_cursor.execute("""
                INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
                VALUES (%s, %s, %s)
            """, (db_employee_regular['id'], db_event['id'], db_booth_cashier['id']))

    def test_booth_assigned_cannot_become_event_manager(self, db_cursor, db_employee_regular,
                                                        db_event, db_booth_cashier):
        """Zaměstnanec přiřazený ke stánku nemůže být event_manager."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
        """, (db_employee_regular['id'], db_event['id'], db_booth_cashier['id']))

        with pytest.raises(RaiseException, match="cannot assign event_manager"):
            db_cursor.execute("""
                INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id, role)
                VALUES (%s, %s, NULL, 'event_manager')
            """, (db_employee_regular['id'], db_event['id']))

    def test_role_booth_type_mismatch_rejected(self, db_cursor, db_employee_regular,
                                                db_event, db_booth_cashier):
        """Role neshodující se s booth_type vyvolá výjimku."""
        with pytest.raises(RaiseException, match="do not match"):
            db_cursor.execute("""
                INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id, role)
                VALUES (%s, %s, %s, 'seller')
            """, (db_employee_regular['id'], db_event['id'], db_booth_cashier['id']))
