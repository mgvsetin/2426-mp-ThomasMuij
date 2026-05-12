"""Konfigurace testů a sdílené fixtures pro cashier_app."""

import pytest
import os
from contextlib import contextmanager
from typing import Any, Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient
from psycopg import Connection, Cursor
from psycopg_pool import ConnectionPool

from cashier_app import create_app


# ---------------------------------------------------------------------------
# Flask aplikace a testovací klient
# ---------------------------------------------------------------------------

@pytest.fixture()
def app() -> Generator[Flask, None, None]:
    """Vytvoří Flask aplikaci nakonfigurovanou pro testování."""
    test_config = {
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'DATABASE_CONNINFO': 'dbname=test_db host=localhost user=test password=test',
        'PASSWORD_HASHER_PARAMETERS': {
            'time_cost': 1,
            'memory_cost': 1024,
            'parallelism': 1,
            'hash_len': 16,
            'salt_len': 8,
        },
        'READER_INFO': {
            'serial_port_options': {
                'baudRate': 9600,
                'dataBits': 8,
                'stopBits': 1,
                'parity': 'none',
                'flowControl': 'none',
            }
        },
        'MAX_UNDO_CHANGES': 30,
        'UNDO_TIME_LIMIT_MINUTES': 60,
        'REFUND_TIME_LIMIT_MINUTES': 5,
        'UPLOAD_IMAGE_PIXEL_LIMIT': 50_000_000,
        'ALLOWED_IMAGE_EXTENSIONS': {'jpeg', 'png', 'webp'},
        'ALLOWED_IMAGE_MIME_TYPES': {'image/jpeg', 'image/png', 'image/webp'},
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': False,
        'SESSION_ENFORCE_UA': False,
        'SESSION_ENFORCE_IP': False,
        'SESSION_MAX_INACTIVE_DAYS': 7,
        'SCHEDULER_ENABLED': False,
    }

    # Nahrazení databázového poolu a plánovače, abychom se nepřipojovali ke skutečné DB
    with patch('cashier_app.db.init_app'), \
         patch('cashier_app.scheduler.init_scheduler'):
        application = create_app(test_config)

    # Použití výchozího in-memory rozhraní pro relace v testech
    from flask.sessions import SecureCookieSessionInterface
    application.session_interface = SecureCookieSessionInterface()

    yield application


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Testovací klient Flask."""
    return app.test_client()


@pytest.fixture()
def app_context(app: Flask) -> Generator[Flask, None, None]:
    """Aktivuje aplikační kontext pro testy, které ho vyžadují."""
    with app.app_context():
        yield app


# ---------------------------------------------------------------------------
# Mock databázového poolu
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_pool() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Vrátí mock ConnectionPool, jehož .connection() kontextový manažer
    poskytne mock připojení s mock kurzorem."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    pool.connection.return_value.__enter__ = MagicMock(return_value=conn)
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)

    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    return pool, conn, cur


# ---------------------------------------------------------------------------
# Pomocné konstanty a funkce pro mock testy
# ---------------------------------------------------------------------------

ADMIN_EMPLOYEE = {
    'id': str(uuid4()),
    'username': 'admin',
    'email': 'admin@example.com',
    'is_admin': True,
}

REGULAR_EMPLOYEE = {
    'id': str(uuid4()),
    'username': 'cashier1',
    'email': 'cashier1@example.com',
    'is_admin': False,
}

SAMPLE_EVENT = {
    'id': str(uuid4()),
    'name': 'TestEvent',
    'start_at': '2025-01-01T00:00:00+00:00',
    'end_at': None,
}

SAMPLE_BOOTH_SELLER = {
    'id': str(uuid4()),
    'name': 'Booth1',
    'event_id': SAMPLE_EVENT['id'],
    'booth_type': 'seller',
}

SAMPLE_BOOTH_CASHIER = {
    'id': str(uuid4()),
    'name': 'CashierBooth',
    'event_id': SAMPLE_EVENT['id'],
    'booth_type': 'cashier',
}


def mock_auth(employee):
    """Mock pro load_logged_in_employee — nastaví g.employee."""
    def _side_effect():
        from flask import g
        g.employee = employee
        return employee
    return patch('cashier_app.auth.load_logged_in_employee', side_effect=_side_effect)


def mock_event(event):
    """Mock pro load_selected_event — nastaví g.event."""
    def _side_effect():
        from flask import g
        g.event = event
        return event
    return patch('cashier_app.employee_events_booths.load_selected_event', side_effect=_side_effect)


def mock_booth(booth):
    """Mock pro load_selected_booth — nastaví g.booth."""
    def _side_effect():
        from flask import g
        g.booth = booth
        return booth
    return patch('cashier_app.employee_events_booths.load_selected_booth', side_effect=_side_effect)


def set_session(client: FlaskClient, employee: dict[str, Any] | None = None, event: dict[str, Any] | None = None, booth: dict[str, Any] | None = None) -> None:
    """Pomocná funkce pro nastavení hodnot relace na testovacím klientovi."""
    with client.session_transaction() as sess:
        if employee:
            sess['employee_id'] = employee['id']
        if event:
            sess['event_id'] = event['id']
        if booth:
            sess['booth_id'] = booth['id']


# ---------------------------------------------------------------------------
# Databázové fixtures pro integrační testy (pytest -m db)
# ---------------------------------------------------------------------------

DB_TEST_CONNINFO = os.environ.get('TEST_DATABASE_CONNINFO', (
    "dbname=cashier_app_test host=localhost user=postgres password=heslo123 port=5432"
))


@pytest.fixture(scope="session")
def _db_pool() -> Generator[ConnectionPool, None, None]:
    """Interní session-scoped pool — inicializuje schéma jednou za celý test run."""
    from psycopg.rows import dict_row

    pool = ConnectionPool(
        DB_TEST_CONNINFO,
        kwargs={'row_factory': dict_row},
        min_size=1,
        max_size=3,
        open=True,
    )

    schema_path = os.path.join(os.path.dirname(__file__), '..', 'cashier_app', 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    with pool.connection() as conn:
        previous_autocommit = conn.autocommit
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                DO $$ DECLARE r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            cur.execute(schema_sql)
        conn.autocommit = previous_autocommit

    yield pool
    pool.close()


@pytest.fixture()
def db_conn(_db_pool: ConnectionPool) -> Generator[Connection, None, None]:
    """Poskytne připojení k testovací DB; po testu provede ROLLBACK.

    Veškerá data vložená během testu se automaticky zahodí.
    """
    with _db_pool.connection() as conn:
        conn.autocommit = False
        yield conn
        conn.rollback()


@pytest.fixture()
def db_cursor(db_conn: Connection) -> Generator[Cursor, None, None]:
    """Poskytne kurzor k testovací DB."""
    with db_conn.cursor() as cur:
        yield cur


class _SingleConnPool:
    """Falešný pool, který vždy vrátí stejné připojení.

    Používá se pro API integrační testy — API kód volá get_pool().connection(),
    ale my chceme aby dostal to samé připojení jako test, aby všechno
    běželo v jedné transakci (která se na konci rollbackne).
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @contextmanager
    def connection(self, **kwargs: Any) -> Generator[Connection, None, None]:
        yield self._conn


@pytest.fixture()
def db_pool(db_conn: Connection) -> _SingleConnPool:
    """Vrátí falešný pool, který vždy vrátí db_conn.

    Použití v testech: patch('cashier_app.xxx.get_pool', return_value=db_pool)
    API kód pak dostane stejné připojení jako test setup, všechno v jedné transakci.
    """
    return _SingleConnPool(db_conn)


# ---------------------------------------------------------------------------
# Pomocné DB fixtures pro vkládání testovacích dat
# ---------------------------------------------------------------------------

FAKE_HASH = '$argon2id$v=19$m=1024,t=1,p=1$dGVzdHNhbHQ$dGVzdGhhc2g'


@pytest.fixture()
def db_employee_admin(db_cursor: Cursor) -> dict[str, Any]:
    """Vloží testovacího admin zaměstnance a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO employees (username, email, password_hash, is_admin)
        VALUES ('test_admin', 'test_admin@example.com', %s, TRUE)
        RETURNING *
    """, (FAKE_HASH,))
    return db_cursor.fetchone()


@pytest.fixture()
def db_employee_regular(db_cursor: Cursor, db_employee_admin: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovacího běžného zaměstnance a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO employees (username, email, password_hash, is_admin, created_by)
        VALUES ('test_cashier', 'test_cashier@example.com', %s, FALSE, %s)
        RETURNING *
    """, (FAKE_HASH, db_employee_admin['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_event(db_cursor: Cursor, db_employee_admin: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací aktivní akci a vrátí její data."""
    db_cursor.execute("""
        INSERT INTO events (name, start_at, end_at, created_by)
        VALUES ('Test Event', now() - INTERVAL '1 day', now() + INTERVAL '1 day', %s)
        RETURNING *
    """, (db_employee_admin['id'],))
    return db_cursor.fetchone()


@pytest.fixture()
def db_booth_cashier(db_cursor: Cursor, db_event: dict[str, Any], db_employee_admin: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací pokladní stánek a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO booths (name, event_id, booth_type, created_by)
        VALUES ('Test Cashier Booth', %s, 'cashier', %s)
        RETURNING *
    """, (db_event['id'], db_employee_admin['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_booth_seller(db_cursor: Cursor, db_event: dict[str, Any], db_employee_admin: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací prodejní stánek a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO booths (name, event_id, booth_type, created_by)
        VALUES ('Test Seller Booth', %s, 'seller', %s)
        RETURNING *
    """, (db_event['id'], db_employee_admin['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_user(db_cursor: Cursor) -> dict[str, Any]:
    """Vloží testovacího uživatele a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO users (first_name, last_name, email)
        VALUES ('Test', 'User', 'test.user@example.com')
        RETURNING *
    """)
    return db_cursor.fetchone()


@pytest.fixture()
def db_wallet(db_cursor: Cursor, db_event: dict[str, Any], db_user: dict[str, Any], db_employee_admin: dict[str, Any], db_booth_cashier: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací peněženku a vrátí její data."""
    db_cursor.execute("""
        INSERT INTO wallets (event_id, tag_id, owner_id, created_by)
        VALUES (%s, 'TEST_TAG_001', %s, %s)
        RETURNING *
    """, (db_event['id'], db_user['id'], db_employee_admin['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_employee_role(db_cursor: Cursor, db_employee_admin: dict[str, Any], db_event: dict[str, Any], db_booth_cashier: dict[str, Any]) -> dict[str, Any]:
    """Přiřadí admin zaměstnance k pokladnímu stánku a vrátí roli."""
    db_cursor.execute("""
        INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
        VALUES (%s, %s, %s)
        RETURNING *
    """, (db_employee_admin['id'], db_event['id'], db_booth_cashier['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_employee_seller_role(db_cursor: Cursor, db_employee_admin: dict[str, Any], db_event: dict[str, Any], db_booth_seller: dict[str, Any]) -> dict[str, Any]:
    """Přiřadí admin zaměstnance k prodejnímu stánku a vrátí roli."""
    db_cursor.execute("""
        INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
        VALUES (%s, %s, %s)
        RETURNING *
    """, (db_employee_admin['id'], db_event['id'], db_booth_seller['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_employee_manager_role(db_cursor: Cursor, db_employee_regular: dict[str, Any], db_event: dict[str, Any]) -> dict[str, Any]:
    """Přiřadí běžného zaměstnance jako event managera (booth_id IS NULL) a vrátí roli."""
    db_cursor.execute("""
        INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
        VALUES (%s, %s, NULL)
        RETURNING *
    """, (db_employee_regular['id'], db_event['id']))
    return db_cursor.fetchone()


@pytest.fixture()
def db_product(db_cursor: Cursor, db_event: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací produkt a vrátí jeho data."""
    db_cursor.execute("""
        INSERT INTO products (name, price, event_id)
        VALUES ('Test Product', 50, %s)
        RETURNING *
    """, (db_event['id'],))
    return db_cursor.fetchone()


@pytest.fixture()
def db_category(db_cursor: Cursor, db_event: dict[str, Any]) -> dict[str, Any]:
    """Vloží testovací kategorii a vrátí její data."""
    db_cursor.execute("""
        INSERT INTO categories (name, event_id)
        VALUES ('Test Category', %s)
        RETURNING *
    """, (db_event['id'],))
    return db_cursor.fetchone()


# ---------------------------------------------------------------------------
# Pomocné funkce pro DB-backed API testy (mock auth/event/booth s reálnými daty)
# ---------------------------------------------------------------------------

def _to_str_dict(d: dict[str, Any] | None) -> dict[str, Any] | None:
    """Převede UUID hodnoty ve slovníku na stringy (API kód očekává stringy)."""
    if d is None:
        return None
    return {k: str(v) if hasattr(v, 'hex') else v for k, v in d.items()}


def mock_auth_db(employee_dict: dict[str, Any]):
    """Mock auth s reálnými DB daty."""
    emp = _to_str_dict(employee_dict)
    def _side_effect():
        from flask import g
        g.employee = emp
        return emp
    return patch('cashier_app.auth.load_logged_in_employee', side_effect=_side_effect)


def mock_event_db(event_dict: dict[str, Any]):
    """Mock výběru eventu s reálnými DB daty."""
    ev = _to_str_dict(event_dict)
    def _side_effect():
        from flask import g
        g.event = ev
        return ev
    return patch('cashier_app.employee_events_booths.load_selected_event', side_effect=_side_effect)


def mock_booth_db(booth_dict: dict[str, Any], event_dict: dict[str, Any] | None = None):
    """Mock výběru stánku s reálnými DB daty.

    Volitelně nastaví i g.event — potřebné pro endpointy, které nemají
    samostatný require_event_selected dekorátor (např. wallets).
    """
    bt = _to_str_dict(booth_dict)
    ev = _to_str_dict(event_dict) if event_dict else None
    def _side_effect():
        from flask import g
        if ev is not None:
            g.event = ev
        g.booth = bt
        return bt
    return patch('cashier_app.employee_events_booths.load_selected_booth', side_effect=_side_effect)
