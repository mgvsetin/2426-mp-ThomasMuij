"""Testy pro menší moduly tras: reader_info, stránky smazaných, index."""

import pytest
from unittest.mock import patch
from tests.conftest import ADMIN_EMPLOYEE


# ---------------------------------------------------------------------------
# GET /api/reader/info
# ---------------------------------------------------------------------------

class TestReaderInfo:

    def test_unauthenticated(self, client):
        with patch('cashier_app.reader_info.load_logged_in_employee', return_value=None):
            resp = client.get('/api/reader/info')
            assert resp.status_code == 401

    def test_authenticated_returns_reader_info(self, client, app):
        with patch('cashier_app.reader_info.load_logged_in_employee', return_value=ADMIN_EMPLOYEE):
            resp = client.get('/api/reader/info')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'reader_info' in data


# ---------------------------------------------------------------------------
# GET /deleted/users  a  GET /deleted/events  (stránkové trasy)
# ---------------------------------------------------------------------------

class TestDeletedPages:

    def test_deleted_users_page(self, client):
        resp = client.get('/deleted/users')
        assert resp.status_code == 200

    def test_deleted_events_page(self, client):
        resp = client.get('/deleted/events')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /  (úvodní stránka)
# ---------------------------------------------------------------------------

class TestIndexPage:

    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
