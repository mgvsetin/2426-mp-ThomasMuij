"""Tests for cashier_app.undo_and_redo route handlers and helpers."""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE

from cashier_app.undo_and_redo import (
    _get_change_type,
    _order_changes_for_undo,
    _order_changes_for_redo,
)


def _mock_auth(employee):
    return patch('cashier_app.undo_and_redo.load_logged_in_employee', return_value=employee)


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
        # old_values falsy (None), new_values truthy → insert
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
        # deletes + updates + reversed inserts
        # no deletes or updates → just reversed inserts
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
        with _mock_auth(None):
            resp = client.post('/api/undo')
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/redo
# ---------------------------------------------------------------------------

class TestRedo:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/redo')
            assert resp.status_code == 401
