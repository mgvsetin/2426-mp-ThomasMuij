"""Testy pro obslužnou funkci trasy cashier_app.paste (vkládání dat)."""

import pytest
from contextlib import ExitStack
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import (
    ADMIN_EMPLOYEE, REGULAR_EMPLOYEE,
    _to_str_dict, mock_auth_db,
)


def _mock_auth(employee):
    return patch('cashier_app.paste.load_logged_in_employee', return_value=employee)


VALID_DATA_TO_COPY = {
    'eventIds': [],
    'boothIds': [],
    'productIds': [],
    'categoryIds': [],
    'managerIds': [],
    'employeesToAssignToTargetBooths': [],
    'employeeIds': [],
}


# ---------------------------------------------------------------------------
# POST /api/paste
# ---------------------------------------------------------------------------

class TestPaste:

    def test_unauthenticated(self, client):
        with _mock_auth(None):
            resp = client.post('/api/paste', json={})
            assert resp.status_code == 401

    def test_non_json_body(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', data='not json',
                               content_type='application/x-www-form-urlencoded')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_mimetype'

    def test_invalid_json_body(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste',
                               data='{{invalid',
                               content_type='application/json')
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_request_body'

    def test_missing_targets(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={'dataToCopy': VALID_DATA_TO_COPY})
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_targets'

    def test_new_events_by_non_admin_forbidden(self, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 403
            assert resp.get_json()['error'] == 'insufficient_privileges'

    def test_new_employees_by_non_admin_forbidden(self, client):
        with _mock_auth(REGULAR_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 403
            assert resp.get_json()['error'] == 'insufficient_privileges'

    def test_invalid_targets_not_dict(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': 123,
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_targets'

    def test_invalid_targets_missing_keys(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': {'wrongKey': []},
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_targets'

    def test_empty_target_ids(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': {'eventIds': [], 'boothIds': []},
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'missing_targets'

    def test_missing_data_to_copy(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                # dataToCopy vynecháno
            })
            # admin → targets projde, poté chybí dataToCopy
            assert resp.status_code == 400

    def test_invalid_target_uuid(self, client):
        with _mock_auth(ADMIN_EMPLOYEE):
            resp = client.post('/api/paste', json={
                'targets': {'eventIds': ['not-a-uuid'], 'boothIds': []},
                'dataToCopy': VALID_DATA_TO_COPY,
            })
            assert resp.status_code == 400
            assert resp.get_json()['error'] == 'invalid_targets'


# ===========================================================================
# DB-backed integrační testy (pytest -m db)
# ===========================================================================

def _make_data_to_copy(event_ids=None, booth_ids=None, product_ids=None,
                       category_ids=None, manager_ids=None,
                       employees_to_assign=None, employee_ids=None):
    """Sestaví dataToCopy payload se stringovými UUID."""
    return {
        'eventIds': [str(i) for i in (event_ids or [])],
        'boothIds': [str(i) for i in (booth_ids or [])],
        'productIds': [str(i) for i in (product_ids or [])],
        'categoryIds': [str(i) for i in (category_ids or [])],
        'managerIds': [str(i) for i in (manager_ids or [])],
        'employeesToAssignToTargetBooths': [str(i) for i in (employees_to_assign or [])],
        'employeeIds': [str(i) for i in (employee_ids or [])],
    }


def _mock_paste_auth_db(employee_dict):
    """Mock auth pro paste endpoint (patchuje přímo v paste modulu)."""
    emp = _to_str_dict(employee_dict)
    def _side_effect():
        from flask import g
        g.employee = emp
        return emp
    return patch('cashier_app.paste.load_logged_in_employee', side_effect=_side_effect)


@pytest.mark.db
class TestPasteNewEmployeesDB:
    """Integrační testy: paste newEmployees."""

    def _paste_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.paste.get_pool', return_value=db_pool))
        return stack

    def _undo_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def test_paste_single_employee(self, client, db_pool, db_cursor, db_employee_admin):
        """Paste jednoho zaměstnance vytvoří kopii s _copy username."""
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_admin['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM employees WHERE username = 'test_admin_copy' AND deleted_at IS NULL")
        cloned = db_cursor.fetchone()
        assert cloned is not None
        assert cloned['id'] != db_employee_admin['id']
        assert cloned['email'] == 'test_admin_copy@example.com'
        assert cloned['is_admin'] == db_employee_admin['is_admin']

    def test_paste_employee_undo(self, client, db_pool, db_cursor, db_employee_admin):
        """Undo po paste zaměstnance soft-deletne klonovaného zaměstnance."""
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_admin['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM employees WHERE username = 'test_admin_copy' AND deleted_at IS NULL")
        assert db_cursor.fetchone() is not None

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT deleted_at FROM employees WHERE username = 'test_admin_copy'")
        row = db_cursor.fetchone()
        assert row is not None
        assert row['deleted_at'] is not None

    def test_paste_employee_undo_redo(self, client, db_pool, db_cursor, db_employee_admin):
        """Redo po undo obnoví klonovaného zaměstnance."""
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_admin['id']]),
            })

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            client.post('/api/undo')

        db_cursor.execute(
            "SELECT deleted_at FROM employees WHERE username = 'test_admin_copy'")
        assert db_cursor.fetchone()['deleted_at'] is not None

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT deleted_at FROM employees WHERE username = 'test_admin_copy'")
        assert db_cursor.fetchone()['deleted_at'] is None

    def test_paste_employee_with_role(self, client, db_pool, db_cursor,
                                     db_employee_admin, db_employee_regular,
                                     db_event, db_booth_seller):
        """Paste zaměstnance zkopíruje i jeho role v event/booth."""
        # Přiřadit regulárnímu zaměstnanci roli u seller booth
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
        """, (db_employee_regular['id'], db_event['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_regular['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM employees WHERE username = 'test_cashier_copy' AND deleted_at IS NULL")
        cloned = db_cursor.fetchone()
        assert cloned is not None

        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id = %s
        """, (cloned['id'], db_event['id'], db_booth_seller['id']))
        role = db_cursor.fetchone()
        assert role is not None

    def test_paste_employee_with_role_undo_redo(self, client, db_pool, db_cursor,
                                                db_employee_admin, db_employee_regular,
                                                db_event, db_booth_seller):
        """Undo/redo paste zaměstnance s rolí odstraní/obnoví roli i zaměstnance."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
        """, (db_employee_regular['id'], db_event['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_regular['id']]),
            })

        db_cursor.execute(
            "SELECT id FROM employees WHERE username = 'test_cashier_copy' AND deleted_at IS NULL")
        cloned_id = db_cursor.fetchone()['id']

        # Undo — zaměstnanec soft-deleted, role smazána (cascade / undo)
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT deleted_at FROM employees WHERE id = %s", (cloned_id,))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute("""
            SELECT 1 FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id = %s
        """, (cloned_id, db_event['id'], db_booth_seller['id']))
        assert db_cursor.fetchone() is None

        # Redo — zaměstnanec obnoven, role znovu vložena
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT deleted_at FROM employees WHERE id = %s", (cloned_id,))
        assert db_cursor.fetchone()['deleted_at'] is None

        db_cursor.execute("""
            SELECT 1 FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id = %s
        """, (cloned_id, db_event['id'], db_booth_seller['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_multiple_employees(self, client, db_pool, db_cursor,
                                      db_employee_admin, db_employee_regular):
        """Paste dvou zaměstnanců najednou vytvoří dvě kopie."""
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEmployees',
                'dataToCopy': _make_data_to_copy(
                    employee_ids=[db_employee_admin['id'], db_employee_regular['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM employees WHERE username LIKE '%_copy%' AND deleted_at IS NULL")
        assert db_cursor.fetchone()['cnt'] == 2


@pytest.mark.db
class TestPasteToNewEventsDB:
    """Integrační testy: paste to newEvents."""

    def _paste_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.paste.get_pool', return_value=db_pool))
        return stack

    def _undo_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def test_paste_event_creates_clone(self, client, db_pool, db_cursor,
                                       db_employee_admin, db_event):
        """Paste s targets=newEvents vytvoří kopii události."""
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT * FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        cloned = db_cursor.fetchone()
        assert cloned is not None
        assert cloned['id'] != db_event['id']

    def test_paste_event_with_booth_and_product(self, client, db_pool, db_cursor,
                                                db_employee_admin, db_event,
                                                db_booth_seller, db_product):
        """Paste události s prodejním stánkem a produktem klonuje vše."""
        # Přiřadit produkt k booth
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        new_event = db_cursor.fetchone()
        assert new_event is not None

        # Ověřit klonovaný booth
        db_cursor.execute(
            "SELECT id FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (new_event['id'],))
        new_booth = db_cursor.fetchone()
        assert new_booth is not None

        # Ověřit klonovaný produkt
        db_cursor.execute(
            "SELECT id FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (new_event['id'],))
        new_product = db_cursor.fetchone()
        assert new_product is not None

        # Ověřit product_booth_link
        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (new_product['id'], new_booth['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_event_undo(self, client, db_pool, db_cursor,
                              db_employee_admin, db_event, db_booth_seller,
                              db_product, db_category):
        """Undo paste události soft-deletne novou událost a všechny klonované entity."""
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))
        db_cursor.execute("""
            INSERT INTO category_booth_link (category_id, booth_id)
            VALUES (%s, %s)
        """, (db_category['id'], db_booth_seller['id']))
        db_cursor.execute("""
            INSERT INTO category_product_link (category_id, product_id)
            VALUES (%s, %s)
        """, (db_category['id'], db_product['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        new_event_id = db_cursor.fetchone()['id']

        # Undo
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s", (new_event_id,))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (new_event_id,))
        assert db_cursor.fetchone()['cnt'] == 0

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (new_event_id,))
        assert db_cursor.fetchone()['cnt'] == 0

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM categories WHERE event_id = %s AND deleted_at IS NULL",
            (new_event_id,))
        assert db_cursor.fetchone()['cnt'] == 0

    def test_paste_event_undo_redo(self, client, db_pool, db_cursor,
                                   db_employee_admin, db_event,
                                   db_booth_seller, db_product):
        """Redo po undo obnoví celou klonovanou událost se stánkem a produktem."""
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy'")
        new_event_id = db_cursor.fetchone()['id']

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            client.post('/api/undo')

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s", (new_event_id,))
        assert db_cursor.fetchone()['deleted_at'] is None

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (new_event_id,))
        assert db_cursor.fetchone()['cnt'] >= 1

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (new_event_id,))
        assert db_cursor.fetchone()['cnt'] >= 1


@pytest.mark.db
class TestPasteToExistingEventsDB:
    """Integrační testy: paste do existujících událostí."""

    def _paste_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.paste.get_pool', return_value=db_pool))
        return stack

    def _undo_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def test_paste_booth_and_product_to_existing_event(self, client, db_pool, db_cursor,
                                                        db_employee_admin, db_event,
                                                        db_booth_seller, db_product):
        """Paste stánku a produktu do jiné existující události."""
        # Vytvořit cílovou událost
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Target Event', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target_event = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': {
                    'eventIds': [str(target_event['id'])],
                    'boothIds': [],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']],
                    product_ids=[db_product['id']]),
            })
            assert resp.status_code == 200

        # Ověřit klonovaný booth v cílové události
        db_cursor.execute(
            "SELECT * FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        cloned_booth = db_cursor.fetchone()
        assert cloned_booth is not None
        assert cloned_booth['name'] == 'Test Seller Booth'

        # Ověřit klonovaný produkt v cílové události
        db_cursor.execute(
            "SELECT * FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        cloned_product = db_cursor.fetchone()
        assert cloned_product is not None
        assert cloned_product['name'] == 'Test Product'

    def test_paste_to_existing_event_undo(self, client, db_pool, db_cursor,
                                          db_employee_admin, db_event,
                                          db_booth_seller, db_product):
        """Undo paste do existující události odstraní klonované entity."""
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Target Undo', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target_event = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': {
                    'eventIds': [str(target_event['id'])],
                    'boothIds': [],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']],
                    product_ids=[db_product['id']]),
            })

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 1

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 0

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 0

    def test_paste_to_existing_event_undo_redo(self, client, db_pool, db_cursor,
                                               db_employee_admin, db_event,
                                               db_booth_seller, db_product):
        """Redo po undo obnoví entity v existující události."""
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Target Redo', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target_event = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': {
                    'eventIds': [str(target_event['id'])],
                    'boothIds': [],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']],
                    product_ids=[db_product['id']]),
            })

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            client.post('/api/undo')

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 0

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 1

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        assert db_cursor.fetchone()['cnt'] == 1

    def test_paste_category_with_product_link_to_event(self, client, db_pool, db_cursor,
                                                       db_employee_admin, db_event,
                                                       db_booth_seller, db_product,
                                                       db_category):
        """Paste kategorie s vazbou na produkt do jiné události zachová link."""
        db_cursor.execute("""
            INSERT INTO category_product_link (category_id, product_id)
            VALUES (%s, %s)
        """, (db_category['id'], db_product['id']))

        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Cat Link Event', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target_event = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': {
                    'eventIds': [str(target_event['id'])],
                    'boothIds': [],
                },
                'dataToCopy': _make_data_to_copy(
                    product_ids=[db_product['id']],
                    category_ids=[db_category['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        new_product = db_cursor.fetchone()
        assert new_product is not None

        db_cursor.execute(
            "SELECT id FROM categories WHERE event_id = %s AND deleted_at IS NULL",
            (target_event['id'],))
        new_category = db_cursor.fetchone()
        assert new_category is not None

        db_cursor.execute("""
            SELECT 1 FROM category_product_link
            WHERE category_id = %s AND product_id = %s
        """, (new_category['id'], new_product['id']))
        assert db_cursor.fetchone() is not None


@pytest.mark.db
class TestPasteToBoothsDB:
    """Integrační testy: paste do stánků."""

    def _paste_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.paste.get_pool', return_value=db_pool))
        return stack

    def _undo_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def test_paste_product_to_booth_same_event(self, client, db_pool, db_cursor,
                                               db_employee_admin, db_event,
                                               db_booth_seller, db_product):
        """Paste produktu ze stejného eventu do seller booth vytvoří product_booth_link."""
        # Vytvořit druhý seller booth ve stejném eventu
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Second Seller', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        second_booth = db_cursor.fetchone()

        # Přiřadit produkt k prvnímu booth
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': {
                    'eventIds': [],
                    'boothIds': [str(second_booth['id'])],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']]),
            })
            assert resp.status_code == 200

        # Produkt existuje v product_booth_link pro druhý booth
        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (db_product['id'], second_booth['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_product_to_booth_cross_event(self, client, db_pool, db_cursor,
                                                db_employee_admin, db_event,
                                                db_booth_seller, db_product):
        """Paste produktu do booth v jiném eventu klonuje produkt a přiřadí."""
        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        # Vytvořit druhou událost s seller boothem
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Other Event', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        other_event = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Other Seller', %s, 'seller', %s) RETURNING *
        """, (other_event['id'], db_employee_admin['id']))
        other_booth = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': {
                    'eventIds': [],
                    'boothIds': [str(other_booth['id'])],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']]),
            })
            assert resp.status_code == 200

        # Klonovaný produkt vytvořen v other_event
        db_cursor.execute(
            "SELECT id, name FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (other_event['id'],))
        cloned_product = db_cursor.fetchone()
        assert cloned_product is not None
        assert cloned_product['name'] == 'Test Product'

        # Link na other_booth
        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (cloned_product['id'], other_booth['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_to_booth_undo_redo(self, client, db_pool, db_cursor,
                                      db_employee_admin, db_event,
                                      db_booth_seller, db_product):
        """Undo/redo paste do booth ze stejného eventu."""
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Undo Redo Seller', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        target_booth = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO product_booth_link (product_id, booth_id)
            VALUES (%s, %s)
        """, (db_product['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': {
                    'eventIds': [],
                    'boothIds': [str(target_booth['id'])],
                },
                'dataToCopy': _make_data_to_copy(
                    booth_ids=[db_booth_seller['id']]),
            })

        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (db_product['id'], target_booth['id']))
        assert db_cursor.fetchone() is not None

        # Undo
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (db_product['id'], target_booth['id']))
        assert db_cursor.fetchone() is None

        # Redo
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        db_cursor.execute("""
            SELECT 1 FROM product_booth_link
            WHERE product_id = %s AND booth_id = %s
        """, (db_product['id'], target_booth['id']))
        assert db_cursor.fetchone() is not None


@pytest.mark.db
class TestPasteComplexDB:
    """Komplexní integrační testy: paste s více entitami a vazbami."""

    def _paste_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.paste.get_pool', return_value=db_pool))
        return stack

    def _undo_patches(self, db_pool):
        stack = ExitStack()
        stack.enter_context(patch('cashier_app.undo_and_redo.get_pool', return_value=db_pool))
        stack.enter_context(patch('cashier_app.undo_and_redo.delete_unused_images'))
        return stack

    def test_paste_full_event_with_all_links(self, client, db_pool, db_cursor,
                                             db_employee_admin, db_event):
        """Paste kompletní události: 2 stánky, 3 produkty, 2 kategorie, všechny linky."""
        # Vytvořit 2 seller booths
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Booth A', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        booth_a = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('Booth B', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        booth_b = db_cursor.fetchone()

        # Vytvořit 3 produkty
        products = []
        for name, price in [('Beer', 50), ('Wine', 80), ('Water', 20)]:
            db_cursor.execute("""
                INSERT INTO products (name, price, event_id)
                VALUES (%s, %s, %s) RETURNING *
            """, (name, price, db_event['id']))
            products.append(db_cursor.fetchone())

        # Vytvořit 2 kategorie
        db_cursor.execute("""
            INSERT INTO categories (name, event_id) VALUES ('Alcohol', %s) RETURNING *
        """, (db_event['id'],))
        cat_alcohol = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO categories (name, event_id) VALUES ('Non-Alcohol', %s) RETURNING *
        """, (db_event['id'],))
        cat_nonalc = db_cursor.fetchone()

        # product_booth_link: Beer + Wine → Booth A; Water → Booth B
        db_cursor.execute("INSERT INTO product_booth_link VALUES (%s, %s)",
                          (products[0]['id'], booth_a['id']))
        db_cursor.execute("INSERT INTO product_booth_link VALUES (%s, %s)",
                          (products[1]['id'], booth_a['id']))
        db_cursor.execute("INSERT INTO product_booth_link VALUES (%s, %s)",
                          (products[2]['id'], booth_b['id']))

        # category_booth_link: Alcohol → Booth A; Non-Alcohol → Booth B
        db_cursor.execute("INSERT INTO category_booth_link VALUES (%s, %s)",
                          (cat_alcohol['id'], booth_a['id']))
        db_cursor.execute("INSERT INTO category_booth_link VALUES (%s, %s)",
                          (cat_nonalc['id'], booth_b['id']))

        # category_product_link: Beer, Wine → Alcohol; Water → Non-Alcohol
        db_cursor.execute("INSERT INTO category_product_link VALUES (%s, %s)",
                          (cat_alcohol['id'], products[0]['id']))
        db_cursor.execute("INSERT INTO category_product_link VALUES (%s, %s)",
                          (cat_alcohol['id'], products[1]['id']))
        db_cursor.execute("INSERT INTO category_product_link VALUES (%s, %s)",
                          (cat_nonalc['id'], products[2]['id']))

        # --- Paste to new event ---
        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        new_event = db_cursor.fetchone()
        assert new_event is not None
        ne_id = new_event['id']

        # 2 booths klonováno
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 2

        # 3 products klonováno
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 3

        # 2 categories klonováno
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM categories WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 2

        # product_booth_links klonováno (3 linky)
        db_cursor.execute("""
            SELECT count(*) AS cnt FROM product_booth_link pb
            JOIN booths b ON b.id = pb.booth_id
            WHERE b.event_id = %s
        """, (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 3

        # category_booth_links klonováno (2 linky)
        db_cursor.execute("""
            SELECT count(*) AS cnt FROM category_booth_link cb
            JOIN booths b ON b.id = cb.booth_id
            WHERE b.event_id = %s
        """, (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 2

        # category_product_links klonováno (3 linky)
        db_cursor.execute("""
            SELECT count(*) AS cnt FROM category_product_link cp
            JOIN products p ON p.id = cp.product_id
            WHERE p.event_id = %s
        """, (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 3

    def test_paste_full_event_undo_removes_everything(self, client, db_pool, db_cursor,
                                                      db_employee_admin, db_event):
        """Undo celého paste kompletní události odstraní vše co bylo vytvořeno."""
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('S1', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        booth = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO products (name, price, event_id)
            VALUES ('P1', 100, %s) RETURNING *
        """, (db_event['id'],))
        product = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO categories (name, event_id)
            VALUES ('C1', %s) RETURNING *
        """, (db_event['id'],))
        category = db_cursor.fetchone()

        db_cursor.execute("INSERT INTO product_booth_link VALUES (%s, %s)",
                          (product['id'], booth['id']))
        db_cursor.execute("INSERT INTO category_booth_link VALUES (%s, %s)",
                          (category['id'], booth['id']))
        db_cursor.execute("INSERT INTO category_product_link VALUES (%s, %s)",
                          (category['id'], product['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(event_ids=[db_event['id']]),
            })

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        ne_id = db_cursor.fetchone()['id']

        # Undo
        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/undo')
            assert resp.status_code == 200

        # Vše soft-deleted
        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s", (ne_id,))
        assert db_cursor.fetchone()['deleted_at'] is not None

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 0

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 0

        db_cursor.execute(
            "SELECT count(*) AS cnt FROM categories WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 0

        # Linky smazány (cascade z soft-deleted entit)
        db_cursor.execute("""
            SELECT count(*) AS cnt FROM product_booth_link pb
            JOIN booths b ON b.id = pb.booth_id
            WHERE b.event_id = %s
        """, (ne_id,))
        assert db_cursor.fetchone()['cnt'] == 0

    def test_paste_full_event_undo_redo_restores_everything(self, client, db_pool, db_cursor,
                                                            db_employee_admin, db_event):
        """Redo po undo kompletní události obnoví vše zpět."""
        db_cursor.execute("""
            INSERT INTO booths (name, event_id, booth_type, created_by)
            VALUES ('RestoreBooth', %s, 'seller', %s) RETURNING *
        """, (db_event['id'], db_employee_admin['id']))
        booth = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO products (name, price, event_id)
            VALUES ('RestoreProduct', 30, %s) RETURNING *
        """, (db_event['id'],))
        product = db_cursor.fetchone()

        db_cursor.execute("""
            INSERT INTO categories (name, event_id)
            VALUES ('RestoreCategory', %s) RETURNING *
        """, (db_event['id'],))
        category = db_cursor.fetchone()

        db_cursor.execute("INSERT INTO product_booth_link VALUES (%s, %s)",
                          (product['id'], booth['id']))
        db_cursor.execute("INSERT INTO category_product_link VALUES (%s, %s)",
                          (category['id'], product['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(event_ids=[db_event['id']]),
            })

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy'")
        ne_id = db_cursor.fetchone()['id']

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            client.post('/api/undo')

        with mock_auth_db(db_employee_admin), self._undo_patches(db_pool):
            resp = client.post('/api/redo')
            assert resp.status_code == 200

        # Událost obnovena
        db_cursor.execute("SELECT deleted_at FROM events WHERE id = %s", (ne_id,))
        assert db_cursor.fetchone()['deleted_at'] is None

        # Booth obnoven
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM booths WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] >= 1

        # Produkt obnoven
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM products WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] >= 1

        # Kategorie obnovena
        db_cursor.execute(
            "SELECT count(*) AS cnt FROM categories WHERE event_id = %s AND deleted_at IS NULL",
            (ne_id,))
        assert db_cursor.fetchone()['cnt'] >= 1

    def test_paste_manager_to_new_event(self, client, db_pool, db_cursor,
                                        db_employee_admin, db_employee_regular,
                                        db_event):
        """Paste události s managerem zkopíruje managerovu roli do nové události."""
        # Přiřadit regulárního zaměstnance jako event managera
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, NULL)
        """, (db_employee_regular['id'], db_event['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']],
                    manager_ids=[db_employee_regular['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        new_event = db_cursor.fetchone()
        assert new_event is not None

        # Manager přiřazen k nové události
        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id IS NULL
        """, (db_employee_regular['id'], new_event['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_employee_booth_role_to_new_event(self, client, db_pool, db_cursor,
                                                    db_employee_admin, db_employee_regular,
                                                    db_event, db_booth_seller):
        """Paste události klonuje booth role zaměstnanců do nové události."""
        db_cursor.execute("""
            INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
            VALUES (%s, %s, %s)
        """, (db_employee_regular['id'], db_event['id'], db_booth_seller['id']))

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': 'newEvents',
                'dataToCopy': _make_data_to_copy(
                    event_ids=[db_event['id']]),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT id FROM events WHERE name = 'Test Event_copy' AND deleted_at IS NULL")
        new_event = db_cursor.fetchone()
        ne_id = new_event['id']

        # Klonovaný booth v nové události
        db_cursor.execute(
            "SELECT id FROM booths WHERE event_id = %s AND name = 'Test Seller Booth' AND deleted_at IS NULL",
            (ne_id,))
        new_booth = db_cursor.fetchone()
        assert new_booth is not None

        # Zaměstnanec přiřazen ke klonovanému booth
        db_cursor.execute("""
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s AND booth_id = %s
        """, (db_employee_regular['id'], ne_id, new_booth['id']))
        assert db_cursor.fetchone() is not None

    def test_paste_unique_name_collision(self, client, db_pool, db_cursor,
                                        db_employee_admin, db_event, db_product):
        """Paste produktu dvakrát do stejného eventu vytvoří _copy a _copy2 názvy."""
        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Collision Event', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target = db_cursor.fetchone()

        for _ in range(2):
            with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
                resp = client.post('/api/paste', json={
                    'targets': {
                        'eventIds': [str(target['id'])],
                        'boothIds': [],
                    },
                    'dataToCopy': _make_data_to_copy(
                        product_ids=[db_product['id']]),
                })
                assert resp.status_code == 200

        db_cursor.execute(
            "SELECT name FROM products WHERE event_id = %s AND deleted_at IS NULL ORDER BY name",
            (target['id'],))
        names = [r['name'] for r in db_cursor.fetchall()]
        assert 'Test Product' in names
        assert 'Test Product_copy' in names

    def test_paste_preserves_product_prices(self, client, db_pool, db_cursor,
                                            db_employee_admin, db_event):
        """Paste zachová ceny produktů."""
        prices = [10, 99, 250, -30]
        product_ids = []
        for i, price in enumerate(prices):
            db_cursor.execute("""
                INSERT INTO products (name, price, event_id)
                VALUES (%s, %s, %s) RETURNING id
            """, (f'Price_{i}', price, db_event['id']))
            product_ids.append(db_cursor.fetchone()['id'])

        db_cursor.execute("""
            INSERT INTO events (name, start_at, created_by)
            VALUES ('Price Event', now(), %s) RETURNING *
        """, (db_employee_admin['id'],))
        target = db_cursor.fetchone()

        with _mock_paste_auth_db(db_employee_admin), self._paste_patches(db_pool):
            resp = client.post('/api/paste', json={
                'targets': {
                    'eventIds': [str(target['id'])],
                    'boothIds': [],
                },
                'dataToCopy': _make_data_to_copy(product_ids=product_ids),
            })
            assert resp.status_code == 200

        db_cursor.execute(
            "SELECT price FROM products WHERE event_id = %s AND deleted_at IS NULL ORDER BY name",
            (target['id'],))
        cloned_prices = sorted([r['price'] for r in db_cursor.fetchall()])
        assert cloned_prices == sorted(prices)
