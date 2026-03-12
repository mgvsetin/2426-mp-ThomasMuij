"""Testy pro modul cashier_app.events.booths (stánky v rámci akcí)."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from flask import g
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT, mock_auth


# ---------------------------------------------------------------------------
# POST /api/events/booths/create
# ---------------------------------------------------------------------------

class TestAddBooth:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/booths/create')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': '',
                'type': 'seller',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_missing_type(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': 'TestBooth',
                'type': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_type'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_invalid_type(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': 'TestBooth',
                'type': 'invalid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_type'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_cashier_with_products(self, mock_mgr, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': 'CashierBooth',
                'type': 'cashier',
                'products': str(uuid4()),
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'cashier_cannot_have_products_or_categories'


# ---------------------------------------------------------------------------
# POST /api/events/booths/edit
# ---------------------------------------------------------------------------

class TestEditBooth:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.post('/api/events/booths/edit')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/edit', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# DELETE /api/events/booths/delete
# ---------------------------------------------------------------------------

class TestDeleteBooth:

    def test_unauthenticated(self, client):
        with mock_auth(None):
            resp = client.delete('/api/events/booths/delete')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/booths/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/booths/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# GET /api/events/booths/products-categories
# ---------------------------------------------------------------------------

class TestGetProductsAndCategories:

    def _mock_event(self, event):
        def _side_effect():
            g.event = event
            return event
        return patch('cashier_app.employee_events_booths.load_selected_event', side_effect=_side_effect)

    def _mock_booth(self, booth):
        def _side_effect():
            g.booth = booth
            return booth
        return patch('cashier_app.employee_events_booths.load_selected_booth', side_effect=_side_effect)

    def test_unauthenticated(self, client):
        with mock_auth(None), self._mock_event(SAMPLE_EVENT), self._mock_booth(None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 401

    def test_no_event(self, client):
        with mock_auth(ADMIN_EMPLOYEE), self._mock_event(None), self._mock_booth(None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_no_booth(self, client):
        with mock_auth(ADMIN_EMPLOYEE), self._mock_event(SAMPLE_EVENT), self._mock_booth(None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

from tests.conftest import mock_auth_db, mock_event_db, mock_booth_db


@pytest.mark.db
class TestBoothsDB:
    """Integrační testy stánků s reálnou DB."""

    def _patches(self, db_pool):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.events.booths.get_pool', return_value=db_pool))
        return stack

    def test_create_seller_booth(self, client, db_pool, db_cursor,
                                  db_employee_admin, db_event, db_product, db_category):
        """Vytvoření prodejního stánku s produkty a kategoriemi."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(db_event['id']),
                'name': 'New Seller Booth',
                'type': 'seller',
                'products': str(db_product['id']),
                'categories': str(db_category['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM booths WHERE name = 'New Seller Booth' AND deleted_at IS NULL")
        booth = db_cursor.fetchone()
        assert booth is not None
        assert booth['booth_type'] == 'seller'

        db_cursor.execute(
            "SELECT * FROM product_booth_link WHERE booth_id = %s", (booth['id'],))
        assert db_cursor.fetchone() is not None

        db_cursor.execute(
            "SELECT * FROM category_booth_link WHERE booth_id = %s", (booth['id'],))
        assert db_cursor.fetchone() is not None

    def test_create_cashier_booth(self, client, db_pool, db_cursor,
                                   db_employee_admin, db_event):
        """Vytvoření pokladního stánku."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(db_event['id']),
                'name': 'New Cashier Booth',
                'type': 'cashier',
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM booths WHERE name = 'New Cashier Booth' AND deleted_at IS NULL")
        booth = db_cursor.fetchone()
        assert booth is not None
        assert booth['booth_type'] == 'cashier'

    def test_duplicate_booth_name(self, client, db_pool, db_cursor,
                                   db_employee_admin, db_event, db_booth_seller):
        """Duplicitní název stánku v rámci události vrátí 409."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(db_event['id']),
                'name': db_booth_seller['name'],
                'type': 'seller',
            })
            assert resp.status_code == 409
            assert resp.get_json()['error'] == 'booth_name_taken'

    def test_edit_booth(self, client, db_pool, db_cursor,
                         db_employee_admin, db_event, db_booth_seller):
        """Úprava stánku přes API."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.post('/api/events/booths/edit', data={
                'id': str(db_booth_seller['id']),
                'name': 'Updated Booth Name',
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT name FROM booths WHERE id = %s",
                          (db_booth_seller['id'],))
        assert db_cursor.fetchone()['name'] == 'Updated Booth Name'

    def test_delete_booth(self, client, db_pool, db_cursor,
                           db_employee_admin, db_event, db_booth_seller):
        """Smazání stánku (soft-delete)."""
        with mock_auth_db(db_employee_admin), self._patches(db_pool):
            resp = client.delete('/api/events/booths/delete', data={
                'id': str(db_booth_seller['id']),
            })
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM booths WHERE id = %s",
                          (db_booth_seller['id'],))
        assert db_cursor.fetchone()['deleted_at'] is not None

    def test_get_products_and_categories(self, client, db_pool, db_cursor,
                                          db_employee_admin, db_event,
                                          db_booth_seller, db_product, db_category):
        """Získání produktů a kategorií pro stánek."""
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        db_cursor.execute("""
            INSERT INTO category_booth_link (category_id, booth_id)
            VALUES (%s, %s)
        """, (db_category['id'], db_booth_seller['id']))

        with mock_auth_db(db_employee_admin), \
             mock_event_db(db_event), \
             mock_booth_db(db_booth_seller, db_event), \
             self._patches(db_pool):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'products' in data
            assert 'categories' in data
            assert len(data['products']) == 1
            assert data['products'][0]['name'] == 'Test Product'
            assert len(data['categories']) == 1
            assert data['categories'][0]['name'] == 'Test Category'
