"""Testy modulu cashier_app.session_api pro spravu relace."""

import pytest
from unittest.mock import patch
from tests.conftest import set_session


pytestmark = pytest.mark.db


class TestSessionInfo:

    def test_no_session(self, client):
        """Bez nastavenych session hodnot vrati vsechny polozky jako None."""
        with patch('cashier_app.auth.get_pool'), \
             patch('cashier_app.employee_events_booths.get_pool'), \
             patch('cashier_app.session_api.get_pool'):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee'] is None
        assert data['event'] is None
        assert data['booth'] is None

    def test_employee_only(self, client, db_pool, db_employee_admin):
        """Session s employee_id vrati data zamestance, event a booth jsou None."""
        set_session(client, employee=db_employee_admin)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee'] is not None
        assert data['employee']['username'] == 'test_admin'
        assert data['employee']['is_admin'] is True
        assert data['event'] is None
        assert data['booth'] is None

    def test_employee_and_event(self, client, db_pool, db_employee_admin, db_event):
        """Session s employee_id a event_id vrati zamestance i udalost."""
        set_session(client, employee=db_employee_admin, event=db_event)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee']['username'] == 'test_admin'
        assert data['event'] is not None
        assert data['event']['name'] == 'Test Event'
        assert data['booth'] is None

    def test_full_session(self, client, db_pool, db_employee_admin,
                          db_event, db_booth_seller):
        """Session se vsemi hodnotami vrati zamestance, udalost i stanek."""
        set_session(client, employee=db_employee_admin, event=db_event,
                    booth=db_booth_seller)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee']['username'] == 'test_admin'
        assert data['event']['name'] == 'Test Event'
        assert data['booth']['name'] == 'Test Seller Booth'
        assert data['booth']['booth_type'] == 'seller'

    def test_full_session_cashier_booth(self, client, db_pool, db_employee_admin,
                                        db_event, db_booth_cashier):
        """Session s pokladnim stankem vrati spravny booth_type."""
        set_session(client, employee=db_employee_admin, event=db_event,
                    booth=db_booth_cashier)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['booth']['name'] == 'Test Cashier Booth'
        assert data['booth']['booth_type'] == 'cashier'

    def test_is_event_manager_flag(self, client, db_pool, db_cursor,
                                   db_employee_admin, db_event):
        """Zamestanec s roli event_manager ma is_event_manager=True."""
        # Prirazeni jako event manager (booth_id IS NULL = manager)
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, NULL)
        """, (db_employee_admin['id'], db_event['id']))

        set_session(client, employee=db_employee_admin, event=db_event)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee']['is_event_manager'] is True

    def test_not_event_manager(self, client, db_pool, db_employee_admin,
                               db_event, db_booth_seller, db_employee_role):
        """Zamestanec prirazeny jen ke stanku nema is_event_manager."""
        set_session(client, employee=db_employee_admin, event=db_event)
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee']['is_event_manager'] is False

    def test_invalid_employee_id_in_session(self, client, db_pool):
        """Neexistujici employee_id v session vrati employee=None."""
        from uuid import uuid4
        with client.session_transaction() as sess:
            sess['employee_id'] = str(uuid4())
        with patch('cashier_app.auth.get_pool', return_value=db_pool), \
             patch('cashier_app.employee_events_booths.get_pool', return_value=db_pool), \
             patch('cashier_app.session_api.get_pool', return_value=db_pool):
            resp = client.get('/api/session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['employee'] is None
        assert data['event'] is None
        assert data['booth'] is None
