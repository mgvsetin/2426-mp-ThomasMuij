"""Tests for cashier_app.utils.general module."""

import pytest
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch
from psycopg import IntegrityError

from cashier_app.utils.general import (
    convert_uuids_to_str,
    get_employee_lock_key,
    client_ip_from_request,
    get_constraint_name,
)


# ---------------------------------------------------------------------------
# convert_uuids_to_str
# ---------------------------------------------------------------------------

class TestConvertUuidsToStr:

    def test_uuid_converted_to_string(self):
        uid = UUID('550e8400-e29b-41d4-a716-446655440000')
        assert convert_uuids_to_str(uid) == '550e8400-e29b-41d4-a716-446655440000'

    def test_string_unchanged(self):
        assert convert_uuids_to_str('hello') == 'hello'

    def test_int_unchanged(self):
        assert convert_uuids_to_str(42) == 42

    def test_none_unchanged(self):
        assert convert_uuids_to_str(None) is None

    def test_dict_with_uuid_values(self):
        uid = uuid4()
        result = convert_uuids_to_str({'id': uid, 'name': 'test'})
        assert result == {'id': str(uid), 'name': 'test'}

    def test_list_with_uuids(self):
        uid1, uid2 = uuid4(), uuid4()
        result = convert_uuids_to_str([uid1, uid2])
        assert result == [str(uid1), str(uid2)]

    def test_tuple_with_uuids(self):
        uid = uuid4()
        result = convert_uuids_to_str((uid, 'a'))
        assert result == (str(uid), 'a')

    def test_nested_dict_list(self):
        uid = uuid4()
        data = {'items': [{'id': uid}]}
        result = convert_uuids_to_str(data)
        assert result == {'items': [{'id': str(uid)}]}

    def test_empty_structures(self):
        assert convert_uuids_to_str({}) == {}
        assert convert_uuids_to_str([]) == []
        assert convert_uuids_to_str(()) == ()


# ---------------------------------------------------------------------------
# get_employee_lock_key
# ---------------------------------------------------------------------------

class TestGetEmployeeLockKey:

    def test_returns_int(self):
        uid = uuid4()
        key = get_employee_lock_key(uid)
        assert isinstance(key, int)

    def test_same_inputs_produce_same_key(self):
        uid = uuid4()
        key1 = get_employee_lock_key(uid, 1001)
        key2 = get_employee_lock_key(uid, 1001)
        assert key1 == key2

    def test_different_namespaces_produce_different_keys(self):
        uid = uuid4()
        key1 = get_employee_lock_key(uid, 1001)
        key2 = get_employee_lock_key(uid, 2002)
        assert key1 != key2

    def test_different_uuids_produce_different_keys(self):
        uid1 = uuid4()
        uid2 = uuid4()
        key1 = get_employee_lock_key(uid1)
        key2 = get_employee_lock_key(uid2)
        assert key1 != key2

    def test_string_namespace(self):
        uid = uuid4()
        key = get_employee_lock_key(uid, 'undo')
        assert isinstance(key, int)

    def test_key_fits_in_signed_64_bit(self):
        uid = uuid4()
        key = get_employee_lock_key(uid)
        assert -(2**63) <= key < 2**63


# ---------------------------------------------------------------------------
# client_ip_from_request
# ---------------------------------------------------------------------------

class TestClientIpFromRequest:

    def test_uses_x_forwarded_for_first_ip(self, app):
        with app.test_request_context(
            headers={'X-Forwarded-For': '1.2.3.4, 5.6.7.8'}
        ):
            assert client_ip_from_request() == '1.2.3.4'

    def test_uses_x_forwarded_for_single_ip(self, app):
        with app.test_request_context(
            headers={'X-Forwarded-For': '10.0.0.1'}
        ):
            assert client_ip_from_request() == '10.0.0.1'

    def test_falls_back_to_remote_addr(self, app):
        with app.test_request_context():
            result = client_ip_from_request()
            assert isinstance(result, str)

    def test_empty_xff_falls_back(self, app):
        with app.test_request_context(
            headers={'X-Forwarded-For': ''}
        ):
            result = client_ip_from_request()
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_constraint_name
# ---------------------------------------------------------------------------

class TestGetConstraintName:

    def test_returns_constraint_name(self):
        error = MagicMock(spec=IntegrityError)
        error.diag = MagicMock()
        error.diag.constraint_name = 'unique_index_employees_username_active'
        result = get_constraint_name(error)
        assert result == 'unique_index_employees_username_active'

    def test_returns_none_when_no_diag(self):
        error = MagicMock(spec=IntegrityError)
        error.diag = None
        result = get_constraint_name(error)
        assert result is None

    def test_returns_none_on_exception(self):
        error = MagicMock(spec=IntegrityError)
        type(error).diag = property(lambda s: (_ for _ in ()).throw(RuntimeError))
        result = get_constraint_name(error)
        assert result is None
