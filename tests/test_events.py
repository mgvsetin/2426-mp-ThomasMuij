"""Testy obsluznych funkci tras modulu cashier_app.events."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT,
    mock_auth, mock_event,
)


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------

class TestGetEventsToManage:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get('/api/events')
            assert resp.status_code == 401

    @patch('cashier_app.events.get_pool')
    def test_admin_gets_events(self, mock_pool, client):
        events_list = [
            {'id': str(uuid4()), 'name': 'Event1', 'start_at': None,
             'end_at': None, 'created_at': '2025-01-01'}
        ]
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = events_list
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.get('/api/events')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'events' in data
            assert len(data['events']) == 1

    @patch('cashier_app.events.get_pool')
    def test_non_admin_gets_their_events(self, mock_pool, client):
        events_list = [
            {'id': str(uuid4()), 'name': 'MyEvent', 'start_at': None,
             'end_at': None, 'created_at': '2025-01-01'}
        ]
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchall.return_value = events_list
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.get('/api/events')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'events' in data


# ---------------------------------------------------------------------------
# GET /api/events/<event_id>
# ---------------------------------------------------------------------------

class TestGetEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get(f'/api/events/{uuid4()}')
            assert resp.status_code == 401

    @patch('cashier_app.events.is_manager', return_value=False)
    def test_non_admin_non_manager_forbidden(self, mock_is_mgr, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.get(f'/api/events/{uuid4()}')
            assert resp.status_code == 403

    @patch('cashier_app.events.get_pool')
    def test_event_not_found(self, mock_pool, client):
        mock_cur = MagicMock()
        mock_cur.execute.return_value.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.return_value.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.return_value.connection.return_value.__exit__ = MagicMock(return_value=False)

        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.get(f'/api/events/{uuid4()}')
            assert resp.status_code == 404
            assert resp.get_json()['error'] == 'event_not_found'


# ---------------------------------------------------------------------------
# POST /api/events/create
# ---------------------------------------------------------------------------

class TestAddEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/create')
            assert resp.status_code == 401

    def test_non_admin_forbidden(self, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/create')
            assert resp.status_code == 403

    def test_missing_name(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/create', data={
                'name': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    @patch('cashier_app.events.validate_event_or_booth_name', return_value=(False, ['name_too_long']))
    def test_invalid_name(self, mock_validate, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/create', data={
                'name': 'x' * 300,
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'name_too_long'

    def test_invalid_start_at(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/create', data={
                'name': 'ValidEvent',
                'start-at': 'not-a-date',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_start_at'


# ---------------------------------------------------------------------------
# POST /api/events/edit
# ---------------------------------------------------------------------------

class TestEditEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/edit')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/edit', data={'id': 'not-a-uuid'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'

    def test_missing_name(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/edit', data={
                'id': str(uuid4()),
                'name': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    def test_start_at_after_end_at(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/edit', data={
                'id': str(uuid4()),
                'name': 'ValidEvent',
                'start-at': '2025-12-31T00:00:00+00:00',
                'end-at': '2025-01-01T00:00:00+00:00',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_start_at_end_at_dates'


# ---------------------------------------------------------------------------
# DELETE /api/events/delete
# ---------------------------------------------------------------------------

class TestDeleteEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.delete('/api/events/delete')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/delete', data={'id': 'bad'})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# GET /api/events/deleted
# ---------------------------------------------------------------------------

class TestGetDeletedEvents:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get('/api/events/deleted')
            assert resp.status_code == 401

    def test_non_admin_forbidden(self, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.get('/api/events/deleted')
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/events/restore
# ---------------------------------------------------------------------------

class TestRestoreEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/restore')
            assert resp.status_code == 401

    def test_non_admin_forbidden(self, client):
        with mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/events/restore')
            assert resp.status_code == 403

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/restore', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'


# ---------------------------------------------------------------------------
# GET /api/events/wallets
# ---------------------------------------------------------------------------

class TestGetEventWallets:

    def test_unauthenticated(self, client):
        with mock_auth(None), mock_event(None):
            resp = client.get('/api/events/wallets')
            assert resp.status_code == 401

    def test_no_selected_event(self, client):
        with mock_auth(ADMIN_EMPLOYEE), mock_event(None):
            resp = client.get('/api/events/wallets')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'


# ---------------------------------------------------------------------------
# GET /api/events/<event_id>/users/<user_id>/transaction-history
# ---------------------------------------------------------------------------

class TestGetUserTransactionHistoryForEvent:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get(f'/api/events/{uuid4()}/users/{uuid4()}/transaction-history')
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/events/<event_id>/transaction-history
# ---------------------------------------------------------------------------

class TestGetEventTransactionHistory:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get(f'/api/events/{uuid4()}/transaction-history')
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/events/<event_id>/statistics
# ---------------------------------------------------------------------------

class TestGetEventStatistics:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.get(f'/api/events/{uuid4()}/statistics')
            assert resp.status_code == 401


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestEventsDB:
    """Integrační testy událostí s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.get_pool', return_value=db_pool))
        return stack

    def test_create_event(self, client, db_pool, db_cursor, db_employee_admin):
        """Vytvoření události přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/create', data={
                'name': 'New Test Event',
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM events WHERE name = 'New Test Event' AND deleted_at IS NULL")
        assert db_cursor.fetchone() is not None

    def test_create_event_duplicate_name(self, client, db_pool, db_cursor,
                                          db_employee_admin, db_event):
        """Duplicitní název události vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/create', data={
                'name': db_event['name'],
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'event_name_taken'

    def test_edit_event(self, client, db_pool, db_cursor, db_employee_admin, db_event):
        """Úprava události přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/edit', data={
                'id': str(db_event['id']),
                'name': 'Updated Event Name',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name FROM events WHERE id = %s", (db_event['id'],))
        assert db_cursor.fetchone()['name'] == 'Updated Event Name'

    def test_delete_event_cascades(self, client, db_pool, db_cursor,
                                    db_employee_admin, db_event, db_booth_seller,
                                    db_product, db_category):
        """Smazání události kaskádově smaže potomky."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/events/delete', data={
                'id': str(db_event['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s",
                          (db_event['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute("SELECT deleted_at FROM booths WHERE id = %s",
                          (db_booth_seller['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute("SELECT deleted_at FROM products WHERE id = %s",
                          (db_product['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute("SELECT deleted_at FROM categories WHERE id = %s",
                          (db_category['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_get_events(self, client, db_pool, db_cursor, db_employee_admin, db_event):
        """Získání seznamu událostí."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.get('/api/events')
            assert resp.status_code == 200
            events = resp.get_json()['events']
            assert any(str(db_event['id']) == str(e['id']) for e in events)

    def test_get_deleted_events(self, client, db_pool, db_cursor,
                                 db_employee_admin, db_event):
        """Smazaná událost se objeví v seznamu smazaných."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.delete('/api/events/delete', data={
                'id': str(db_event['id']),
            })
            resp = client.get('/api/events/deleted')
            assert resp.status_code == 200
            events = resp.get_json()['events']
            assert any(str(db_event['id']) == str(e['id']) for e in events)

    def test_restore_event(self, client, db_pool, db_cursor,
                            db_employee_admin, db_event):
        """Obnovení smazané události."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.delete('/api/events/delete', data={
                'id': str(db_event['id']),
            })
            resp = client.post('/api/events/restore', data={
                'event-id': str(db_event['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s",
                          (db_event['id'],))
        assert db_cursor.fetchone()['deleted_at'] is None

    def test_restore_event_name_conflict(self, client, db_pool, db_cursor,
                                          db_employee_admin, db_event):
        """Obnovení při konfliktu jména bez force vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.delete('/api/events/delete', data={
                'id': str(db_event['id']),
            })
            client.post('/api/events/create', data={
                'name': db_event['name'],
            })
            resp = client.post('/api/events/restore', data={
                'event-id': str(db_event['id']),
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'event_name_taken'

    def test_restore_event_force_name_conflict(self, client, db_pool, db_cursor,
                                                db_employee_admin, db_event):
        """Obnovení s force při konfliktu jména přejmenuje událost."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            client.delete('/api/events/delete', data={
                'id': str(db_event['id']),
            })
            client.post('/api/events/create', data={
                'name': db_event['name'],
            })
            resp = client.post('/api/events/restore', data={
                'event-id': str(db_event['id']),
                'force': 'true',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name, deleted_at FROM events WHERE id = %s",
                          (db_event['id'],))
        restored = db_cursor.fetchone()
        assert restored['deleted_at'] is None
        assert restored['name'] != db_event['name']
