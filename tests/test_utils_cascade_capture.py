"""Testy modulu cashier_app.utils.cascade_capture pro serializaci dat."""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, date, time, timezone

from cashier_app.utils.cascade_capture import (
    convert_dict_to_serializable,
)


class TestConvertDictToSerializable:

    def test_uuid_to_string(self):
        uid = uuid4()
        result = convert_dict_to_serializable({'id': uid})
        assert result['id'] == str(uid)

    def test_datetime_to_iso(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = convert_dict_to_serializable({'created_at': dt})
        assert result['created_at'] == dt.isoformat()

    def test_date_to_iso(self):
        d = date(2025, 6, 15)
        result = convert_dict_to_serializable({'start_date': d})
        assert result['start_date'] == '2025-06-15'

    def test_time_to_iso(self):
        t = time(14, 30)
        result = convert_dict_to_serializable({'start_time': t})
        assert result['start_time'] == '14:30:00'

    def test_none_remains_none(self):
        result = convert_dict_to_serializable({'deleted_at': None})
        assert result['deleted_at'] is None

    def test_int_unchanged(self):
        result = convert_dict_to_serializable({'price': 100})
        assert result['price'] == 100

    def test_string_unchanged(self):
        result = convert_dict_to_serializable({'name': 'Beer'})
        assert result['name'] == 'Beer'

    def test_bool_unchanged(self):
        result = convert_dict_to_serializable({'is_admin': True})
        assert result['is_admin'] is True

    def test_nested_list(self):
        uid = uuid4()
        result = convert_dict_to_serializable({'items': [uid, 'text']})
        assert result['items'] == [str(uid), 'text']

    def test_nested_dict(self):
        uid = uuid4()
        result = convert_dict_to_serializable({'inner': {'id': uid}})
        assert result['inner']['id'] == str(uid)

    def test_empty_dict(self):
        assert convert_dict_to_serializable({}) == {}

    def test_mixed_types(self):
        uid = uuid4()
        dt = datetime(2025, 3, 1, tzinfo=timezone.utc)
        data = {
            'id': uid,
            'name': 'Test',
            'price': 50,
            'created_at': dt,
            'deleted_at': None,
            'is_admin': False,
        }
        result = convert_dict_to_serializable(data)
        assert result['id'] == str(uid)
        assert result['name'] == 'Test'
        assert result['price'] == 50
        assert result['created_at'] == dt.isoformat()
        assert result['deleted_at'] is None
        assert result['is_admin'] is False
