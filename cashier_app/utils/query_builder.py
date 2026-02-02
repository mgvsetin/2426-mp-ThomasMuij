

from uuid import UUID
#     try:
#         with get_pool().connection() as conn:
#             with conn.cursor() as cur:
#                 cur.execute(
#                     f'''
#                     INSERT INTO events
#                     ({cols_str})
#                     VALUES ({col_values_placeholders})'''


def get_placeholders_and_params(rows: list[dict], cols: list[str] | None = None):
    """
    Build SQL multi-row placeholders and a flat params list.

    Example:
      rows = [(1, 'a'), (2, 'b')]
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
    placeholders_per_row = '(' + ', '.join(['%s'] * row_len) + ')'
    placeholders = ', '.join([placeholders_per_row] * len(rows))
    params = [row[col] for row in rows for col in cols]

    return placeholders, params


def build_insert_statement(table: str, rows_or_params: list[dict] | dict, returning: list | None=None, on_conflict_do_nothing: list | bool=False):
    '''Warning: Table a columns v params nesmí přijít od uživatele a musí být pouze z bezpečného kódu'''
    if not rows_or_params:
        raise ValueError("nothing to insert")
    
    if isinstance(rows_or_params, dict):
        rows = [rows_or_params]
    else:
        rows = rows_or_params
    
    returning_clause = f'RETURNING {", ".join(returning)}' if returning else ''
    if on_conflict_do_nothing is True:
        conflict_clause = 'ON CONFLICT DO NOTHING'
    elif on_conflict_do_nothing is False:
        conflict_clause = ''
    elif isinstance(on_conflict_do_nothing, list):
        conflict_clause = f'ON CONFLICT ({", ".join(on_conflict_do_nothing)}) DO NOTHING'

    cols = list(rows[0].keys())
    placeholders, params = get_placeholders_and_params(rows, cols)

    sql = f"""
    INSERT INTO {table}
    ({', '.join(cols)})
    VALUES {placeholders}
    {conflict_clause}
    {returning_clause}
    """

    return sql, params


def build_update_statement(table: str, params: dict, target_id: str | UUID, include_deleted_at_is_null=True, returning: list | None=None):
    '''Warning: Table a columns v params nesmí přijít od uživatele a musí být pouze z bezpečného kódu'''
    if not params:
        raise ValueError("no columns to update")
    
    returning_clause = f'RETURNING {", ".join(returning)}' if returning else ''

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])
    params = dict(params)
    params['id'] = target_id

    sql = f"""
    UPDATE {table}
    SET {col_updates_str}
    WHERE id = %(id)s
    {'AND deleted_at IS NULL' if include_deleted_at_is_null else ''}
    {returning_clause}
    """

    return sql, params


def build_delete_statement(table: str, target_id: str | UUID, soft_delete=True):
    '''Warning: Table nesmí přijít od uživatele a musí být pouze z bezpečného kódu'''

    if soft_delete:
        sql = f"""
        UPDATE {table}
        SET deleted_at = now()
        WHERE id = %(id)s
        AND deleted_at IS NULL
        """
    else:
        sql = f"""
        DELETE FROM {table}
        WHERE id = %(id)s
        """

    params = {
        'id': target_id
    }

    return sql, params