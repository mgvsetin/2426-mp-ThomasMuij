"""Testy pro obslužnou funkci trasy cashier_app.paste (vkládání dat)."""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from tests.conftest import ADMIN_EMPLOYEE, REGULAR_EMPLOYEE


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
