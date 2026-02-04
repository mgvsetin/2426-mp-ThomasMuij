from flask import Blueprint, jsonify, url_for, current_app
from psycopg import Cursor, IntegrityError
from psycopg.types.json import Jsonb

from cashier_app.db import get_pool
from cashier_app.auth import load_logged_in_employee
from cashier_app.utils.query_builder import build_update_statement, build_delete_statement, build_insert_statement
from cashier_app.errors import NoChangeToUndoError, ConflictingExistingEmployeeRoles, NoChangeToRedoError, UndoTargetDeletedError, PgTryAdvisoryLockError
from cashier_app.utils.general import get_employee_lock_key

# Configuration for undo/redo limits
MAX_UNDO_CHANGES = 30
UNDO_TIME_LIMIT_MINUTES = 60


bp = Blueprint('undo_and_redo', __name__, url_prefix='/api')


def _cleanup_old_history(cur: Cursor, employee_id):
    """
    Delete change_history rows that are no longer accessible:
    - Rows older than UNDO_TIME_LIMIT_HOURS
    - Rows beyond MAX_UNDO_CHANGES (keeping only the most recent ones)
    """
    # Delete rows older than time limit (and their undo records)

    # tento delete se stane přes cascade v DELETE FROM change_history
    # cur.execute(
    #     '''
    #     DELETE FROM undo_change_history u
    #     USING change_history c
    #     WHERE u.change_history_id = c.id
    #     AND c.performed_by = %s
    #     AND u.occurred_at <= NOW() - INTERVAL '%s hours'
    #     ''',
    #     (employee_id, UNDO_TIME_LIMIT_HOURS))

    params = {
        "employee_id": employee_id,
        "max_undo": MAX_UNDO_CHANGES,
        "undo_time_limit": UNDO_TIME_LIMIT_MINUTES
    }

    cur.execute(
        '''
        DELETE FROM change_history c
        WHERE c.performed_by = %(employee_id)s
        AND c.occurred_at <= NOW() - make_interval(mins => %(undo_time_limit)s)
        AND NOT EXISTS (
            SELECT 1
            FROM undo_change_history u
            WHERE u.change_history_id = c.id
                AND u.occurred_at > NOW() - make_interval(mins => %(undo_time_limit)s)
        )
        ''',
        params)

    cur.execute(
        '''
        DELETE FROM change_history c
        WHERE c.performed_by = %(employee_id)s
        AND c.id NOT IN (
            SELECT id FROM change_history
            WHERE performed_by = %(employee_id)s
            ORDER BY occurred_at DESC
            LIMIT %(max_undo)s
        )
        ''',
        params)


# Link tables that don't have an 'id' column and need special handling
LINK_TABLES = {
    'product_booth_link': ('product_id', 'booth_id'),
    'category_booth_link': ('category_id', 'booth_id'),
    'category_product_link': ('category_id', 'product_id'),
    'employee_event_booth_roles': ('employee_id', 'event_id', 'booth_id'),
}


def save_change(cur: Cursor, changes: list[dict], logged_employee_id):
    """
    Saves changes to change_history for undo capability.
    Clears any pending redo actions for this employee.

    Args:
        cur: Database cursor
        changes: List of change dicts with format:
            {
                'table': str,
                'old_values': dict | None,  # None for INSERT
                'new_values': dict | None   # None for DELETE
            }
        logged_employee_id: UUID of the employee making the change
    """
    if not changes:
        return

    # Filter out no-op changes (where old_values == new_values)
    filtered_changes = [
        change for change in changes
        if change.get('old_values') != change.get('new_values')
    ]

    if not filtered_changes:
        return

    changes = filtered_changes

    # Clear redo history (any undone changes no longer redo-able after new action)
    cur.execute(
        '''
        DELETE FROM undo_change_history u
        USING change_history c
        WHERE u.change_history_id = c.id
        AND c.performed_by = %s
        ''',
        (logged_employee_id,))

    # Clean up old/excess history rows
    _cleanup_old_history(cur, logged_employee_id)

    # Insert the change record
    cur.execute(
        '''
        INSERT INTO change_history (performed_by, changes)
        VALUES (%s, %s)
        ''',
        (logged_employee_id, Jsonb(changes)))


def _get_change_type(change: dict) -> str:
    """Determine the type of change: 'insert', 'update', or 'delete'."""
    old_values = change.get('old_values')
    new_values = change.get('new_values')

    if not old_values and new_values:
        return 'insert'
    elif old_values and new_values:
        return 'update'
    elif old_values and not new_values:
        return 'delete'
    else:
        return 'unknown'


def _delete_link_row(cur: Cursor, table: str, values: dict):
    """Delete a row from a link table using composite key."""
    key_columns = LINK_TABLES[table]
    conditions = []
    params = []
    for col in key_columns:
        if values.get(col) is None:
            conditions.append(f'{col} IS NULL')
        else:
            conditions.append(f'{col} = %s')
            params.append(values[col])

    where_clause = ' AND '.join(conditions)
    cur.execute(f'DELETE FROM {table} WHERE {where_clause}', params)


def _insert_link_row(cur: Cursor, table: str, values: dict):
    """Insert a row into a link table."""

    if table == 'employee_event_booth_roles':
        new_row_is_manager = values['booth_id'] is None

        existing_rows = cur.execute(
            '''
            SELECT * FROM employee_event_booth_roles
            WHERE employee_id = %s AND event_id = %s''',
            (values['employee_id'], values['event_id'])
        ).fetchall()

        if new_row_is_manager:
            for row in existing_rows:
                if row['booth_id'] is not None:
                    raise ConflictingExistingEmployeeRoles()
        else:
            for row in existing_rows:
                if row['booth_id'] is None:
                    raise ConflictingExistingEmployeeRoles()


    sql, query_params = build_insert_statement(table, values, on_conflict_do_nothing=True)

    cur.execute(sql, query_params)


# Mapping from column name to (table, has_deleted_at)
LINK_COLUMN_TO_TABLE = {
    'product_id': ('products', True),
    'booth_id': ('booths', True),
    'category_id': ('categories', True),
    'employee_id': ('employees', True),
    'event_id': ('events', True),
}


def _check_link_references_valid(cur: Cursor, values: dict) -> bool:
    """
    Check if all referenced entities in a link row exist and are not soft-deleted.
    Returns True if all references are valid, False if any are deleted/missing.
    """
    for col, val in values.items():
        if val is None:
            continue  # NULL values are allowed (e.g., booth_id for event managers)

        if col not in LINK_COLUMN_TO_TABLE:
            continue

        ref_table, has_deleted_at = LINK_COLUMN_TO_TABLE[col]

        if has_deleted_at:
            result = cur.execute(
                f'SELECT 1 FROM {ref_table} WHERE id = %s AND deleted_at IS NULL',
                (val,)
            ).fetchone()
        else:
            result = cur.execute(
                f'SELECT 1 FROM {ref_table} WHERE id = %s',
                (val,)
            ).fetchone()

        if not result:
            return False

    return True


def _apply_change_undo(cur: Cursor, change: dict):
    """Apply a single change in undo direction (reverse the operation)."""
    table = change['table']
    old_values = change.get('old_values')
    new_values = change.get('new_values')

    if table in LINK_TABLES:
        # Link table handling
        if old_values and new_values:
            # UPDATE -> restore old values (delete new, insert old)
            _delete_link_row(cur, table, new_values)
            if _check_link_references_valid(cur, old_values):
                _insert_link_row(cur, table, old_values)
        elif not old_values and new_values:
            # INSERT -> delete the inserted row
            _delete_link_row(cur, table, new_values)
        elif old_values and not new_values:
            # DELETE -> re-insert the row (only if referenced entities still exist)
            if _check_link_references_valid(cur, old_values):
                _insert_link_row(cur, table, old_values)
    else:
        # Regular table with 'id' column
        if old_values and new_values:
            # UPDATE -> restore old values
            target_id = new_values['id']

            # Check if entity still exists and is not soft-deleted by another user
            if 'deleted_at' in new_values:
                exists = cur.execute(
                    f'SELECT 1 FROM {table} WHERE id = %s AND deleted_at IS NULL',
                    (target_id,)
                ).fetchone()
                if not exists:
                    raise UndoTargetDeletedError(f'Entity in {table} was deleted by another user')

            # Remove 'id' from old_values for the update
            update_values = {k: v for k, v in old_values.items() if k != 'id'}
            if update_values:
                sql, query_params = build_update_statement(table, update_values, target_id, False)
                cur.execute(sql, query_params)

        elif not old_values and new_values:
            # INSERT -> delete the inserted row
            target_id = new_values['id']
            do_soft_delete = 'deleted_at' in new_values
            sql, query_params = build_delete_statement(table, target_id, do_soft_delete)
            cur.execute(sql, query_params)

        elif old_values and not new_values:
            # DELETE -> restore
            target_id = old_values['id']
            if 'deleted_at' in old_values:
                # Soft delete - just clear deleted_at
                sql, query_params = build_update_statement(table, {'deleted_at': None}, target_id, False)
                cur.execute(sql, query_params)
            else:
                # Hard delete - re-insert the row
                sql, query_params = build_insert_statement(table, old_values)
                cur.execute(sql, query_params)


def _apply_change_redo(cur: Cursor, change: dict):
    """Apply a single change in redo direction (re-apply the operation)."""
    table = change['table']
    old_values = change.get('old_values')
    new_values = change.get('new_values')

    if table in LINK_TABLES:
        # Link table handling
        if old_values and new_values:
            # UPDATE -> apply new values (delete old, insert new)
            _delete_link_row(cur, table, old_values)
            if _check_link_references_valid(cur, new_values):
                _insert_link_row(cur, table, new_values)
        elif not old_values and new_values:
            # INSERT -> re-insert (only if referenced entities still exist)
            if _check_link_references_valid(cur, new_values):
                _insert_link_row(cur, table, new_values)
        elif old_values and not new_values:
            # DELETE -> delete again
            _delete_link_row(cur, table, old_values)
    else:
        # Regular table with 'id' column
        if old_values and new_values:
            # UPDATE -> apply new values
            target_id = old_values['id']

            # Check if entity still exists and is not soft-deleted by another user
            if 'deleted_at' in old_values:
                exists = cur.execute(
                    f'SELECT 1 FROM {table} WHERE id = %s AND deleted_at IS NULL',
                    (target_id,)
                ).fetchone()
                if not exists:
                    raise UndoTargetDeletedError(f'Entity in {table} was deleted by another user')

            update_values = {k: v for k, v in new_values.items() if k != 'id'}
            if update_values:
                sql, query_params = build_update_statement(table, update_values, target_id, False)
                cur.execute(sql, query_params)

        elif not old_values and new_values:
            # INSERT -> re-insert / set deleted_at to NULL
            if 'deleted_at' in new_values.keys():
                sql, query_params = build_update_statement(table, {'deleted_at': None}, new_values['id'], False)
                cur.execute(sql, query_params)
            else:
                sql, query_params = build_insert_statement(table, new_values)
                cur.execute(sql, query_params)

        elif old_values and not new_values:
            # DELETE -> delete again
            target_id = old_values['id']
            if 'deleted_at' in old_values:
                # Soft delete
                sql, query_params = build_delete_statement(table, target_id, soft_delete=True)
                cur.execute(sql, query_params)
            else:
                # Hard delete
                sql, query_params = build_delete_statement(table, target_id, soft_delete=False)
                cur.execute(sql, query_params)


def _order_changes_for_undo(changes: list[dict]) -> list[dict]:
    """
    Order changes correctly for undo operation.

    For undo:
    - DELETE reversals (restorations) must happen in ORIGINAL order (parent before children)
    - INSERT reversals (deletions) must happen in REVERSE order (children before parents)
    - UPDATE reversals can happen in any order

    Strategy: Process deletes first (in original order), then updates, then inserts (in reverse)
    """
    deletes = []
    updates = []
    inserts = []

    for change in changes:
        change_type = _get_change_type(change)
        if change_type == 'delete':
            deletes.append(change)
        elif change_type == 'update':
            updates.append(change)
        elif change_type == 'insert':
            inserts.append(change)

    # Deletes in original order (restore parent before children)
    # Updates in any order
    # Inserts in reverse order (delete children before parents)
    return deletes + updates + list(reversed(inserts))


def _order_changes_for_redo(changes: list[dict]) -> list[dict]:
    """
    Order changes correctly for redo operation.

    For redo:
    - INSERT re-applications must happen in ORIGINAL order (parent before children)
    - DELETE re-applications must happen in REVERSE order (children before parents)
    - UPDATE re-applications can happen in any order

    Strategy: Process inserts first (in original order), then updates, then deletes (in reverse)
    """
    deletes = []
    updates = []
    inserts = []

    for change in changes:
        change_type = _get_change_type(change)
        if change_type == 'delete':
            deletes.append(change)
        elif change_type == 'update':
            updates.append(change)
        elif change_type == 'insert':
            inserts.append(change)

    # Inserts in original order (create parent before children)
    # Updates in any order
    # Deletes in reverse order (delete children before parents)
    return inserts + updates + list(reversed(deletes))


@bp.route('/undo', methods=('POST',))
def undo():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                locked = cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS locked",
                    (get_employee_lock_key(logged_employee['id'], 'undo_redo'),)
                ).fetchone()['locked']

                if not locked:
                    raise PgTryAdvisoryLockError()

                # Clean up old/excess history rows first
                _cleanup_old_history(cur, logged_employee['id'])

                # Find the most recent change that hasn't been undone
                action_to_undo = cur.execute(
                    '''
                    SELECT c.id, c.changes
                    FROM change_history c
                    LEFT JOIN undo_change_history u ON u.change_history_id = c.id
                    WHERE c.performed_by = %s
                    AND u.id IS NULL
                    ORDER BY c.occurred_at DESC
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)).fetchone()

                if not action_to_undo:
                    raise NoChangeToUndoError()

                changes = action_to_undo['changes']

                # Order changes correctly for undo
                ordered_changes = _order_changes_for_undo(changes)

                for change in ordered_changes:
                    _apply_change_undo(cur, change)

                # Record the undo
                cur.execute(
                    '''
                    INSERT INTO undo_change_history (change_history_id)
                    VALUES (%s)
                    ''',
                    (action_to_undo['id'],))

    except NoChangeToUndoError:
        return jsonify(message='no_change_to_undo'), 200
    except (IntegrityError, UndoTargetDeletedError, ConflictingExistingEmployeeRoles) as e:
        current_app.logger.warning('Undo conflict: %s', str(e))
        return jsonify(message='undo_conflict'), 200
    except PgTryAdvisoryLockError:
            return jsonify(error='operation_in_progress'), 409
    except Exception as e:
        current_app.logger.exception('Undo operation failed: %s', str(e))
        return jsonify(error='undo_failed'), 500

    return jsonify(), 200


@bp.route('/redo', methods=('POST',))
def redo():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                locked = cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS locked",
                    (get_employee_lock_key(logged_employee['id'], 'undo_redo'),)
                ).fetchone()['locked']

                if not locked:
                    raise PgTryAdvisoryLockError()

                # Clean up old/excess history rows first
                _cleanup_old_history(cur, logged_employee['id'])

                # Find the most recently undone change
                last_undone = cur.execute(
                    '''
                    SELECT c.id AS change_id, c.changes, u.id AS undo_id
                    FROM undo_change_history u
                    JOIN change_history c ON c.id = u.change_history_id
                    WHERE c.performed_by = %s
                    ORDER BY u.occurred_at DESC
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)).fetchone()

                if not last_undone:
                    raise NoChangeToRedoError()

                changes = last_undone['changes']

                # Order changes correctly for redo
                ordered_changes = _order_changes_for_redo(changes)

                for change in ordered_changes:
                    _apply_change_redo(cur, change)

                # Remove the undo record
                cur.execute(
                    '''
                    DELETE FROM undo_change_history
                    WHERE id = %s
                    ''',
                    (last_undone['undo_id'],))

    except NoChangeToRedoError:
        return jsonify(message='no_change_to_redo'), 200
    except (IntegrityError, UndoTargetDeletedError, ConflictingExistingEmployeeRoles) as e:
        current_app.logger.warning('Redo conflict: %s', str(e))
        return jsonify(message='redo_conflict'), 200
    except PgTryAdvisoryLockError:
            return jsonify(error='operation_in_progress'), 409
    except Exception as e:
        current_app.logger.exception('Redo operation failed: %s', str(e))
        return jsonify(error='redo_failed'), 500

    return jsonify(), 200
