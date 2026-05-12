"""Testy pro modul cashier_app.events.categories (kategorie v rámci akcí)."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT, mock_auth


# ---------------------------------------------------------------------------
# POST /api/events/categories/create
# ---------------------------------------------------------------------------

class TestAddCategory:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/categories/create')
            assert resp.status_code == 401

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/categories/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.categories.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
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
        with mock_auth(None):
            resp = client.post('/api/events/categories/edit')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
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
        with mock_auth(None):
            resp = client.delete('/api/events/categories/delete')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/categories/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestCategoriesDB:
    """Integrační testy kategorií s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.categories.get_pool', return_value=db_pool))
        return stack

    def test_create_category(self, client, db_pool, db_cursor,
                              db_employee_admin, db_event, db_booth_seller, db_product):
        """Vytvoření kategorie s vazbami na stánek a produkt."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/categories/create', data={
                'event-id': str(db_event['id']),
                'name': 'New Category',
                'booths': str(db_booth_seller['id']),
                'products': str(db_product['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM categories WHERE name = 'New Category' AND deleted_at IS NULL")
        cat = db_cursor.fetchone()
        assert cat is not None

        db_cursor.execute(
            "SELECT * FROM category_booth_link WHERE category_id = %s", (cat['id'],))
        assert db_cursor.fetchone() is not None

        db_cursor.execute(
            "SELECT * FROM category_product_link WHERE category_id = %s", (cat['id'],))
        assert db_cursor.fetchone() is not None

    def test_duplicate_category_name(self, client, db_pool, db_cursor,
                                      db_employee_admin, db_event, db_category):
        """Duplicitní název kategorie v rámci události vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/categories/create', data={
                'event-id': str(db_event['id']),
                'name': db_category['name'],
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'category_name_taken'

    def test_edit_category(self, client, db_pool, db_cursor,
                            db_employee_admin, db_event, db_category):
        """Úprava kategorie přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/categories/edit', data={
                'id': str(db_category['id']),
                'name': 'Updated Category',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name FROM categories WHERE id = %s",
                          (db_category['id'],))
        assert db_cursor.fetchone()['name'] == 'Updated Category'

    def test_delete_category(self, client, db_pool, db_cursor,
                              db_employee_admin, db_event, db_category):
        """Smazání kategorie (soft-delete)."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/events/categories/delete', data={
                'id': str(db_category['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM categories WHERE id = %s",
                          (db_category['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None
