"""Tests for cashier_app.events.products module."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE, SAMPLE_EVENT


def _mock_auth(employee):
    return patch('cashier_app.events.products.load_logged_in_employee', return_value=employee)


# ---------------------------------------------------------------------------
# POST /api/events/products/create
# ---------------------------------------------------------------------------

class TestAddProduct:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/events/products/create')
            assert resp.status_code == 401

    def test_invalid_event_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/create', data={
                'event-id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_event_id'

    @patch('cashier_app.events.products.is_manager', return_value=True)
    def test_missing_name(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/events/products/create', data={
                'event-id': str(uuid4()),
                'name': '',
                'price': '10.00',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_name'

    @patch('cashier_app.events.products.is_manager', return_value=True)
    def test_missing_price(self, mock_mgr, client):
        with _mock_auth(ADMIN_EMPLOYEE):
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
        with _mock_auth(None):
            resp = client.post('/api/events/products/edit')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
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
        with _mock_auth(None):
            resp = client.delete('/api/events/products/delete')
            assert resp.status_code == 401

    def test_invalid_id(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.delete('/api/events/products/delete', data={
                'id': 'not-a-uuid',
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_id'
