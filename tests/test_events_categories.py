"""Testy pro modul cashier_app.events.categories (kategorie v rámci akcí)."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT


def _mock_auth(employee):
    return patch('cashier_app.events.categories.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# POST /api/events/categories/create
# ---------------------------------------------------------------------------

class TestAddCategory:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/categories/create')
            assert resp.status_code == 401

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/categories/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.categories.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/categories/create', data={
                'event-id': str(uuid4()),
                'name': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'


# ---------------------------------------------------------------------------
# POST /api/events/categories/edit
# ---------------------------------------------------------------------------

class TestEditCategory:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/categories/edit')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/categories/edit', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# DELETE /api/events/categories/delete
# ---------------------------------------------------------------------------

class TestDeleteCategory:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.delete('/api/events/categories/delete')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/categories/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'
