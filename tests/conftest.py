"""
Shared pytest fixtures for cashier_app tests.

Provides a Flask app, test client, and helpers for simulating
authenticated sessions without needing a real PostgreSQL database.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from cashier_app import create_app


# ---------------------------------------------------------------------------
# Flask application & client
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create a Flask application configured for testing."""
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

    # Patch out the database pool and scheduler so we never touch a real DB
    with patch('cashier_app.db.init_app'), \
         patch('cashier_app.scheduler.init_scheduler'):
        application = create_app(test_config)

    # Use the default in-memory session interface for tests
    from flask.sessions import SecureCookieSessionInterface
    application.session_interface = SecureCookieSessionInterface()

    yield application


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def app_context(app):
    """Push an application context for tests that need it."""
    with app.app_context():
        yield app


# ---------------------------------------------------------------------------
# Mock database pool
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_pool():
    """Return a mock ConnectionPool whose .connection() context manager
    yields a mock connection with a mock cursor."""
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    pool.connection.return_value.__enter__ = MagicMock(return_value=conn)
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)

    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    return pool, conn, cur


# ---------------------------------------------------------------------------
# Authenticated session helpers
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
    """Helper to set session values on the test client."""
    with client.session_transaction() as sess:
        if employee:
            sess['employee_id'] = employee['id']
        if event:
            sess['event_id'] = event['id']
        if booth:
            sess['booth_id'] = booth['id']
