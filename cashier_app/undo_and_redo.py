from flask import Blueprint, jsonify, url_for
from psycopg import Cursor

from cashier_app.db import get_pool
from cashier_app.auth import load_logged_in_employee
from cashier_app.utils.query_builder import build_update_statement, build_delete_statement, build_insert_statement


bp = Blueprint('undo_and_redo', __name__, url_prefix='/api')


def save_change(cur: Cursor, changes, logged_employee_id):
    params = {
        'performed_by': logged_employee_id,
        'changes': changes
    }

    sql, query_params = build_insert_statement('change_history')



@bp.route('undo', methods=('POST',))
def undo():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
#   id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
#   performed_by  uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,

#   target_id     uuid NOT NULL,
#   table_name    text NOT NULL,
#   old_values    jsonb DEFAULT '{}'::jsonb,
#   new_values    jsonb DEFAULT '{}'::jsonb,

#   occurred_at   timestamptz NOT NULL DEFAULT now()
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            action_to_undo = cur.execute(
                '''
                SELECT id, changes
                FROM change_history c
                LEFT JOIN undo_change_history u ON u.change_history_id = c.id
                WHERE c.performed_by = %s
                AND u.id IS NULL
                ORDER BY c.occurred_at DESC
                LIMIT 1
                ''',
                (logged_employee['id'],)).fetchone()
            
            changes = action_to_undo['changes']

            for change in changes:
                table = change['table']
                old_values = change.get('old_values')
                new_values = change.get('new_values')

                

                if old_values and new_values: # update
                    target_id = new_values['id']

                    sql, query_params = build_update_statement(table, old_values, target_id, False)

                    cur.execute(sql, query_params)

                elif not old_values and new_values: # insert
                    target_id = new_values['id']

                    sql, query_params = build_delete_statement(table, target_id)

                    cur.execute(sql, query_params)

                if old_values and not new_values: # delete
                    target_id = old_values['id']

                    if 'deleted_at' in old_values.keys(): # soft delete
                        sql, query_params = build_update_statement(table, {'deleted_at': None}, target_id, False)

                        cur.execute(sql, query_params)
                    else: # normální delete
                        sql, query_params = build_insert_statement(table, old_values)

                        cur.execute(sql, query_params)