"""Testy pro modul cashier_app.events.products (produkty v rámci akcí)."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT, mock_auth


# ---------------------------------------------------------------------------
# POST /api/events/products/create
# ---------------------------------------------------------------------------

class TestAddProduct:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/products/create')
            assert resp.status_code == 401

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.products.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/create', data={
                'event-id': str(uuid4()),
                'name': '',
                'price': '10.00',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    @patch('cashier_app.events.products.is_manager', return_value=True)
    def test_missing_price(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/create', data={
                'event-id': str(uuid4()),
                'name': 'TestProduct',
                'price': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_price'


# ---------------------------------------------------------------------------
# POST /api/events/products/edit
# ---------------------------------------------------------------------------

class TestEditProduct:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/products/edit')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/edit', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# DELETE /api/events/products/delete
# ---------------------------------------------------------------------------

class TestDeleteProduct:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.delete('/api/events/products/delete')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/products/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db


@pytest.mark.db
class TestProductsDB:
    """Integrační testy produktů s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.products.get_pool', return_value=db_pool))
        return stack

    def test_create_product(self, client, db_pool, db_cursor,
                             db_employee_admin, db_event, db_booth_seller):
        """Vytvoření produktu s vazbou na stánek."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/products/create', data={
                'event-id': str(db_event['id']),
                'name': 'New Product',
                'price': '100',
                'booths': str(db_booth_seller['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM products WHERE name = 'New Product' AND deleted_at IS NULL")
        product = db_cursor.fetchone()
        assert product is not None
        assert product['price'] == 100

        db_cursor.execute(
            "SELECT * FROM product_booth_link WHERE product_id = %s", (product['id'],))
        assert db_cursor.fetchone() is not None

    def test_duplicate_product_name(self, client, db_pool, db_cursor,
                                     db_employee_admin, db_event, db_product):
        """Duplicitní název produktu v rámci události vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/products/create', data={
                'event-id': str(db_event['id']),
                'name': db_product['name'],
                'price': '50',
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'product_name_taken'

    def test_edit_product(self, client, db_pool, db_cursor,
                           db_employee_admin, db_event, db_product):
        """Úprava produktu přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/products/edit', data={
                'id': str(db_product['id']),
                'name': 'Updated Product',
                'price': '75',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name, price FROM products WHERE id = %s",
                          (db_product['id'],))
        product = db_cursor.fetchone()
        assert product['name'] == 'Updated Product'
        assert product['price'] == 75

    def test_delete_product(self, client, db_pool, db_cursor,
                             db_employee_admin, db_event, db_product):
        """Smazání produktu (soft-delete)."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/events/products/delete', data={
                'id': str(db_product['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM products WHERE id = %s",
                          (db_product['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None
