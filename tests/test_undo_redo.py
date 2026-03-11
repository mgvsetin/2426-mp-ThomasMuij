"""Testy pro obslužné funkce tras a pomocné funkce modulu cashier_app.undo_and_redo."""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, mock_auth

from cashier_app.undo_and_redo import (
    _get_change_type,
    _order_changes_for_undo,
    _order_changes_for_redo,
)


# ---------------------------------------------------------------------------
# _get_change_type
# ---------------------------------------------------------------------------

class TestGetChangeType:

    def test_insert(self):
        change = {'old_values': None, 'new_values': {'id': '1', 'name': 'A'}}
        assert _get_change_type(change) == 'insert'

    def test_update(self):
        change = {'old_values': {'id': '1', 'name': 'A'}, 'new_values': {'id': '1', 'name': 'B'}}
        assert _get_change_type(change) == 'update'

    def test_delete(self):
        change = {'old_values': {'id': '1', 'name': 'A'}, 'new_values': None}
        assert _get_change_type(change) == 'delete'

    def test_unknown(self):
        change = {'old_values': None, 'new_values': None}
        assert _get_change_type(change) == 'unknown'

    def test_insert_with_empty_old(self):
        # old_values nepravdivé (None), new_values pravdivé → insert
        change = {'old_values': None, 'new_values': {'id': '2'}}
        assert _get_change_type(change) == 'insert'


# ---------------------------------------------------------------------------
# _order_changes_for_undo
# ---------------------------------------------------------------------------

class TestOrderChangesForUndo:

    def _make_insert(self, name='row'):
        return {'table': 't', 'old_values': None, 'new_values': {'id': name}}

    def _make_update(self, name='row'):
        return {'table': 't', 'old_values': {'id': name}, 'new_values': {'id': name, 'x': 1}}

    def _make_delete(self, name='row'):
        return {'table': 't', 'old_values': {'id': name}, 'new_values': None}

    def test_inserts_reversed(self):
        i1 = self._make_insert('i1')
        i2 = self._make_insert('i2')
        ordered = _order_changes_for_undo([i1, i2])
        # smazání + aktualizace + obrácené vložení
        # žádná smazání ani aktualizace → pouze obrácené vložení
        assert ordered == [i2, i1]

    def test_deletes_before_inserts(self):
        ins = self._make_insert()
        delete = self._make_delete()
        ordered = _order_changes_for_undo([ins, delete])
        assert ordered[0] == delete
        assert ordered[-1] == ins

    def test_order_deletes_updates_inserts(self):
        ins = self._make_insert('ins')
        upd = self._make_update('upd')
        delete = self._make_delete('del')
        ordered = _order_changes_for_undo([ins, upd, delete])
        assert ordered == [delete, upd, ins]

    def test_empty_list(self):
        assert _order_changes_for_undo([]) == []


# ---------------------------------------------------------------------------
# _order_changes_for_redo
# ---------------------------------------------------------------------------

class TestOrderChangesForRedo:

    def _make_insert(self, name='row'):
        return {'table': 't', 'old_values': None, 'new_values': {'id': name}}

    def _make_update(self, name='row'):
        return {'table': 't', 'old_values': {'id': name}, 'new_values': {'id': name, 'x': 1}}

    def _make_delete(self, name='row'):
        return {'table': 't', 'old_values': {'id': name}, 'new_values': None}

    def test_inserts_in_original_order(self):
        i1 = self._make_insert('i1')
        i2 = self._make_insert('i2')
        ordered = _order_changes_for_redo([i1, i2])
        assert ordered == [i1, i2]

    def test_deletes_reversed(self):
        d1 = self._make_delete('d1')
        d2 = self._make_delete('d2')
        ordered = _order_changes_for_redo([d1, d2])
        assert ordered == [d2, d1]

    def test_order_inserts_updates_deletes(self):
        ins = self._make_insert('ins')
        upd = self._make_update('upd')
        delete = self._make_delete('del')
        ordered = _order_changes_for_redo([ins, upd, delete])
        assert ordered == [ins, upd, delete]

    def test_empty_list(self):
        assert _order_changes_for_redo([]) == []


# ---------------------------------------------------------------------------
# POST /api/undo
# ---------------------------------------------------------------------------

class TestUndo:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/undo')
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/redo
# ---------------------------------------------------------------------------

class TestRedo:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/redo')
            assert resp.status_code == 401


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestUndoRedoDB:
    """Integrační testy undo/redo s reálnou DB."""

    def _undo_patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def _event_patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.get_pool', return_value=db_pool))
        return stack

    def test_undo_event_create(self, client, db_pool, db_cursor, db_employee_admin):
        """Undo vytvoření události ji soft-deletne."""
        with mock_auth_db(db_employee_admin), self._event_patches(db_pool):
            resp = client.post('/api/events/create', data={
                'name': 'Undo Event',
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Undo Event' AND deleted_at IS NULL")
        event = db_cursor.fetchone()
        assert event is not None

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200
            assert resp.get_json() is None or 'message' not in resp.get_json()

        db_cursor.execute("SELECT deleted_at FROM events WHERE name = 'Undo Event'")
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_redo_event_create(self, client, db_pool, db_cursor, db_employee_admin):
        """Redo po undo obnoví vytvořenou událost."""
        with mock_auth_db(db_employee_admin), self._event_patches(db_pool):
            client.post('/api/events/create', data={
                'name': 'Redo Event',
            })

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            client.post('/api/undo')

        db_cursor.execute("SELECT deleted_at FROM events WHERE name = 'Redo Event'")
        assert db_cursor.fetchone()['deleted_at'] is not None

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM events WHERE name = 'Redo Event'")
        assert db_cursor.fetchone()['deleted_at'] is None

    def test_undo_event_edit(self, client, db_pool, db_cursor,
                              db_employee_admin, db_event):
        """Undo úpravy události obnoví původní hodnoty."""
        original_name = db_event['name']

        with mock_auth_db(db_employee_admin), self._event_patches(db_pool):
            resp = client.post('/api/events/edit', data={
                'id': str(db_event['id']),
                'name': 'Changed Event Name',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name FROM events WHERE id = %s", (db_event['id'],))
        assert db_cursor.fetchone()['name'] == 'Changed Event Name'

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute("SELECT name FROM events WHERE id = %s", (db_event['id'],))
        assert db_cursor.fetchone()['name'] == original_name

    def test_undo_no_change(self, client, db_pool, db_cursor, db_employee_admin):
        """Undo bez dostupných změn vrátí zprávu."""
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200
            assert resp.get_json()['message'] == 'no_change_to_undo'

    def test_redo_no_change(self, client, db_pool, db_cursor, db_employee_admin):
        """Redo bez vrácených změn vrátí zprávu."""
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200
            assert resp.get_json()['message'] == 'no_change_to_redo'
