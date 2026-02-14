"""Tests for cashier_app.utils.query_builder module."""

import pytest
from uuid import uuid4
from psycopg import sql

from cashier_app.utils.query_builder import (
    get_insert_placeholders_and_params,
    build_insert_statement,
    build_update_statement,
    build_delete_statement,
)


# ---------------------------------------------------------------------------
# get_insert_placeholders_and_params
# ---------------------------------------------------------------------------

class TestGetInsertPlaceholdersAndParams:

    def test_single_row(self):
        rows = [{'id': 1, 'name': 'a'}]
        placeholders, params = get_insert_placeholders_and_params(rows)
        assert params == [1, 'a']

    def test_multiple_rows(self):
        rows = [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]
        placeholders, params = get_insert_placeholders_and_params(rows)
        assert params == [1, 'a', 2, 'b']

    def test_empty_raises(self):
        with pytest.raises(ValueError, match='nothing to insert'):
            get_insert_placeholders_and_params([])

    def test_mismatched_columns_raises(self):
        rows = [{'id': 1, 'name': 'a'}, {'id': 2, 'extra': 'b'}]
        with pytest.raises(ValueError, match='same columns'):
            get_insert_placeholders_and_params(rows)

    def test_explicit_cols_order(self):
        rows = [{'b': 2, 'a': 1}]
        placeholders, params = get_insert_placeholders_and_params(rows, cols=['a', 'b'])
        assert params == [1, 2]


# ---------------------------------------------------------------------------
# build_insert_statement
# ---------------------------------------------------------------------------

class TestBuildInsertStatement:

    def test_returns_sql_and_params(self):
        insert_sql, params = build_insert_statement('users', {'name': 'John'})
        assert isinstance(insert_sql, sql.Composed)
        assert params == ['John']

    def test_single_dict_wrapped_to_list(self):
        insert_sql, params = build_insert_statement('test', {'a': 1, 'b': 2})
        assert len(params) == 2

    def test_multiple_rows(self):
        rows = [{'x': 1}, {'x': 2}]
        insert_sql, params = build_insert_statement('test', rows)
        assert params == [1, 2]

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            build_insert_statement('test', {})

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            build_insert_statement('test', [])

    def test_returning_star(self):
        insert_sql, params = build_insert_statement('t', {'a': 1}, returning='*')
        rendered = insert_sql.as_string(None)
        assert 'RETURNING *' in rendered

    def test_returning_columns(self):
        insert_sql, params = build_insert_statement('t', {'a': 1}, returning=['id', 'name'])
        rendered = insert_sql.as_string(None)
        assert 'RETURNING' in rendered

    def test_on_conflict_do_nothing_true(self):
        insert_sql, params = build_insert_statement('t', {'a': 1}, on_conflict_do_nothing=True)
        rendered = insert_sql.as_string(None)
        assert 'ON CONFLICT DO NOTHING' in rendered

    def test_on_conflict_do_nothing_columns(self):
        insert_sql, params = build_insert_statement(
            't', {'a': 1}, on_conflict_do_nothing=['id']
        )
        rendered = insert_sql.as_string(None)
        assert 'ON CONFLICT' in rendered

    def test_schema_table_tuple(self):
        insert_sql, params = build_insert_statement(('public', 'users'), {'name': 'A'})
        rendered = insert_sql.as_string(None)
        assert '"public"' in rendered
        assert '"users"' in rendered

    def test_schema_table_string(self):
        insert_sql, params = build_insert_statement('public.users', {'name': 'A'})
        rendered = insert_sql.as_string(None)
        assert '"public"' in rendered


# ---------------------------------------------------------------------------
# build_update_statement
# ---------------------------------------------------------------------------

class TestBuildUpdateStatement:

    def test_returns_sql_and_params(self):
        uid = uuid4()
        update_sql, params = build_update_statement('users', {'name': 'Bob'}, uid)
        assert isinstance(update_sql, sql.Composed)
        assert params['name'] == 'Bob'
        assert params['id'] == uid

    def test_empty_params_raises(self):
        with pytest.raises(ValueError, match='no columns'):
            build_update_statement('t', {}, uuid4())

    def test_includes_deleted_at_check_by_default(self):
        update_sql, params = build_update_statement('t', {'a': 1}, uuid4())
        rendered = update_sql.as_string(None)
        assert 'deleted_at IS NULL' in rendered

    def test_excludes_deleted_at_check(self):
        update_sql, params = build_update_statement(
            't', {'a': 1}, uuid4(), include_deleted_at_is_null=False
        )
        rendered = update_sql.as_string(None)
        assert 'deleted_at IS NULL' not in rendered

    def test_returning_star(self):
        update_sql, params = build_update_statement('t', {'a': 1}, uuid4(), returning='*')
        rendered = update_sql.as_string(None)
        assert 'RETURNING *' in rendered

    def test_returning_columns(self):
        update_sql, params = build_update_statement(
            't', {'a': 1}, uuid4(), returning=['id']
        )
        rendered = update_sql.as_string(None)
        assert 'RETURNING' in rendered

    def test_multiple_columns(self):
        uid = uuid4()
        update_sql, params = build_update_statement(
            'users', {'name': 'A', 'email': 'a@b.com'}, uid
        )
        rendered = update_sql.as_string(None)
        assert '"name"' in rendered
        assert '"email"' in rendered


# ---------------------------------------------------------------------------
# build_delete_statement
# ---------------------------------------------------------------------------

class TestBuildDeleteStatement:

    def test_soft_delete_default(self):
        uid = uuid4()
        delete_sql, params = build_delete_statement('users', uid)
        rendered = delete_sql.as_string(None)
        assert 'SET deleted_at' in rendered
        assert 'DELETE' not in rendered.split('SET')[0].upper().replace('UPDATE', '')

    def test_hard_delete(self):
        uid = uuid4()
        delete_sql, params = build_delete_statement('users', uid, soft_delete=False)
        rendered = delete_sql.as_string(None)
        assert 'DELETE FROM' in rendered

    def test_params_contain_id(self):
        uid = uuid4()
        delete_sql, params = build_delete_statement('t', uid)
        assert params['id'] == uid

    def test_schema_table(self):
        uid = uuid4()
        delete_sql, params = build_delete_statement(('public', 'users'), uid)
        rendered = delete_sql.as_string(None)
        assert '"public"' in rendered
