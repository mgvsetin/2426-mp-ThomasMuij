

#     try:
#         with get_pool().connection() as conn:
#             with conn.cursor() as cur:
#                 cur.execute(
#                     f'''
#                     INSERT INTO events
#                     ({cols_str})
#                     VALUES ({col_values_placeholders})'''
def build_insert_statement(table, params, returning=None):
    '''Warning: Table a columns v params nesmí přijít od uživatele a musí být pouze z bezpečného kódu'''
    if not params:
        raise ValueError("no columns to insert")

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    returning_clause = f'RETURNING {returning}' if returning else ''

    sql = f'''
    INSERT INTO {table}
    ({cols_str})
    VALUES ({col_values_placeholders})
    {returning_clause}
    '''

    return sql, params


def build_update_statement(table, params, target_id, include_deleted_at_is_null = True):
    '''Warning: Table a columns v params nesmí přijít od uživatele a musí být pouze z bezpečného kódu'''
    if not params:
        raise ValueError("no columns to update")

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])
    params = dict(params)
    params['id'] = target_id

    sql = f"""
    UPDATE {table}
    SET {col_updates_str}
    WHERE id = %(id)s
    {'AND deleted_at IS NULL' if include_deleted_at_is_null else ''}
    """

    return sql, params