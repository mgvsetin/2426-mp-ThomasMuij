

from uuid import UUID
from psycopg import sql
from typing import Literal


def get_insert_placeholders_and_params(rows: list[dict], cols: list[str] | None = None):
    """
    Build SQL multi-row placeholders and a flat params list.

    Example:
      rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
      -> placeholders = '(%s,%s),(%s,%s)'
         params = [1, 'a', 2, 'b']

    Returns:
      (placeholders_string, flat_params_list)
    """
    # handle empty input
    if not rows:
        raise ValueError("nothing to insert")

    if cols is None:
        # jestli není potřeba předurčené pořadí, vem sloupce z prvního
        cols = list(rows[0].keys())

    expected = set(cols)
    for i, row in enumerate(rows):
        if set(row.keys()) != expected:
            raise ValueError(f"All rows must have same columns (row {i} keys differ)")
    
    row_len = len(cols)
    placeholders_per_row = sql.SQL('({placeholders})').format(
        placeholders=sql.SQL(', ').join([sql.Placeholder()] * row_len)
    )
    placeholders = sql.SQL(', ').join([placeholders_per_row] * len(rows))
    params = [row[col] for row in rows for col in cols]

    return placeholders, params


def _format_table_identifier(table: str | tuple[str, str]):
    if isinstance(table, (list, tuple)):
        if len(table) != 2:
            raise ValueError("table tuple must be (schema, table_name)")
        schema, name = table
        return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))
    if isinstance(table, str) and "." in table:
        schema, name = table.split(".", 1)
        return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))

    return sql.Identifier(table)


def build_insert_statement(
        table: str | tuple[str, str],
        rows_or_params: list[dict] | dict,
        returning: list[str] | Literal['*'] | None=None,
        on_conflict_do_nothing: list[str] | bool=False):

    if not rows_or_params:
        raise ValueError("nothing to insert")
    
    if isinstance(rows_or_params, dict):
        rows = [rows_or_params]
    else:
        rows = rows_or_params

    if returning == '*':
        returning_clause = sql.SQL('RETURNING *')
    elif isinstance(returning, (list, tuple)) and returning:
        returning_clause = sql.SQL('RETURNING {columns}').format(
            columns=sql.SQL(', ').join(map(sql.Identifier, returning)))
    else:
        returning_clause = sql.SQL('')

    if on_conflict_do_nothing is True:
        conflict_clause = sql.SQL('ON CONFLICT DO NOTHING')
    elif isinstance(on_conflict_do_nothing, (list, tuple)) and on_conflict_do_nothing:
        conflict_clause = sql.SQL('ON CONFLICT ({cols}) DO NOTHING').format(
            cols=sql.SQL(', ').join(map(sql.Identifier, on_conflict_do_nothing))
        )
    else:
        conflict_clause = sql.SQL('')

    cols = list(rows[0].keys())
    placeholders, params = get_insert_placeholders_and_params(rows, cols)

    table_sql = _format_table_identifier(table)

    insert_sql = sql.SQL("""
    INSERT INTO {table}
    ({values})
    VALUES {placeholders}
    {conflict_clause}
    {returning_clause}
    """).format(
        table=table_sql,
        values=sql.SQL(', ').join(map(sql.Identifier, cols)),
        placeholders=placeholders,
        conflict_clause=conflict_clause,
        returning_clause=returning_clause
    )

    return insert_sql, params


def build_update_statement(
        table: str | tuple[str, str],
        params: dict,
        target_id: str | UUID,
        include_deleted_at_is_null=True,
        returning: list[str] | Literal['*'] | None=None):

    if not params:
        raise ValueError("no columns to update")

    if returning == '*':
        returning_clause = sql.SQL('RETURNING *')
    elif isinstance(returning, (list, tuple)) and returning:
        returning_clause = sql.SQL('RETURNING {columns}').format(
            columns=sql.SQL(', ').join(map(sql.Identifier, returning)))
    else:
        returning_clause = sql.SQL('')

    col_updates_str = sql.SQL(', ').join([sql.SQL('{col} = {placeholder}').format(
        col=sql.Identifier(k),
        placeholder=sql.Placeholder(k))
        for k in params.keys()])

    params = dict(params)
    params['id'] = target_id

    table_sql = _format_table_identifier(table)

    update_sql = sql.SQL("""
    UPDATE {table}
    SET {col_updates_str}
    WHERE id = {id_placeholder}
    {deleted_at_is_null_clause}
    {returning_clause}
    """).format(
        table=table_sql,
        col_updates_str=col_updates_str,
        id_placeholder=sql.Placeholder('id'),
        deleted_at_is_null_clause=sql.SQL('AND deleted_at IS NULL') if include_deleted_at_is_null else sql.SQL(''),
        returning_clause=returning_clause
    )

    return update_sql, params


def build_delete_statement(
        table: str | tuple[str, str],
        target_id: str | UUID,
        soft_delete=True):

    table_sql = _format_table_identifier(table)

    if soft_delete:
        delete_sql = sql.SQL("""
        UPDATE {table}
        SET deleted_at = now()
        WHERE id = {id_placeholder}
        AND deleted_at IS NULL
        """).format(
            table=table_sql,
            id_placeholder=sql.Placeholder('id')
        )
    else:
        delete_sql = sql.SQL("""
        DELETE FROM {table}
        WHERE id = {id_placeholder}
        """).format(
            table=table_sql,
            id_placeholder=sql.Placeholder('id')
        )

    params = {
        'id': target_id
    }

    return delete_sql, params