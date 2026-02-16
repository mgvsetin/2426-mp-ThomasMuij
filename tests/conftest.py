"""Konfigurace testů a sdílené fixtures pro cashier_app."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from cashier_app import create_app


# ---------------------------------------------------------------------------
# Flask aplikace a testovací klient
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
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
def client(app):
    """Testovací klient Flask."""
    return app.test_client()


@pytest.fixture()
def app_context(app):
    """Aktivuje aplikační kontext pro testy, které ho vyžadují."""
    with app.app_context():
        yield app


# ---------------------------------------------------------------------------
# Mock databázového poolu
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_pool():
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
# Pomocné funkce pro autentizovanou relaci
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


def set_session(client, employee=None, event=None, booth=None):
    """Pomocná funkce pro nastavení hodnot relace na testovacím klientovi."""
    with client.session_transaction() as sess:
        if employee:
            sess['employee_id'] = employee['id']
        if event:
            sess['event_id'] = event['id']
        if booth:
            sess['booth_id'] = booth['id']
