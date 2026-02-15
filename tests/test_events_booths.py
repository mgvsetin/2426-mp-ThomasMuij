"""Tests for cashier_app.events.booths module."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT


def _mock_auth(employee):
    return patch('cashier_app.events.booths.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# POST /api/events/booths/create
# ---------------------------------------------------------------------------

class TestAddBooth:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/booths/create')
            assert resp.status_code == 401

    def test_missing_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_event_id'

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': '',
                'type': 'seller',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_missing_type(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': 'TestBooth',
                'type': '',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_type'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_invalid_type(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/create', data={
                'event-id': str(uuid4()),
                'name': 'TestBooth',
                'type': 'invalid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_type'

    @patch('cashier_app.events.booths.is_manager', return_value=True)
    def test_cashier_with_products(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
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
        with _mock_auth(None):
            resp = client.post('/api/events/booths/edit')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/booths/edit', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
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
        with _mock_auth(None):
            resp = client.delete('/api/events/booths/delete')
            assert resp.status_code == 401

    def test_missing_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/booths/delete', data={})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_id'

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/booths/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'


# ---------------------------------------------------------------------------
# GET /api/events/booths/products-categories
# ---------------------------------------------------------------------------

class TestGetProductsAndCategories:

    def test_unauthenticated(self, client):
        with _mock_auth(None), \
             patch('cashier_app.events.booths.load_selected_event', return_value=SAMPLE_EVENT), \
             patch('cashier_app.events.booths.load_selected_booth', return_value=None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 401

    def test_no_event(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.events.booths.load_selected_event', return_value=None), \
             patch('cashier_app.events.booths.load_selected_booth', return_value=None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_event'

    def test_no_booth(self, client):
        with _mock_auth(ADMIN_EMPLOYEE), \
             patch('cashier_app.events.booths.load_selected_event', return_value=SAMPLE_EVENT), \
             patch('cashier_app.events.booths.load_selected_booth', return_value=None):
            resp = client.get('/api/events/booths/products-categories')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'no_selected_booth'
