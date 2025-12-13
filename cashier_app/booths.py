from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.employee_events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.employees import is_manager


api_bp = Blueprint('booths_api', __name__, url_prefix='/api/booths')


@api_bp.route('/create', methods=('POST',))
def add_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    name = request.form.get('name', '').strip()
    booth_type = request.form.get('type', '').strip()

    params = {
        'created_by': logged_employee['id'],
        'event_id': event_id
        }

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if not booth_type:
        return jsonify(error='missing_type'), 400

    if booth_type not in ['seller', 'cashier']:
        return jsonify(error='invalid_type'), 400
    params['booth_type'] = booth_type

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f'''
                    INSERT INTO booths
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    params)
    except IntegrityError as e: #
        # jméno už existuje: detail = unique_index_booths_event_id_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_bp.route('/edit', methods=('POST',))
def edit_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    try:
        booth_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not booth_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_id = cur.execute(f'''
                SELECT event_id
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not event_id:
        return jsonify(error='booth_not_found'), 404
    
    event_id = event_id['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    name = request.form.get('name', '').strip()
    booth_type = request.form.get('type', '').strip()

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if not booth_type:
        return jsonify(error='missing_type'), 400

    if booth_type not in ['seller', 'cashier']:
        return jsonify(error='invalid_type'), 400
    params['booth_type'] = booth_type

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = booth_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f'''
                    UPDATE booths
                    SET {col_updates_str}
                    WHERE id = %(id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {booth_id}')
    except IntegrityError as e:
        # jméno už existuje: detail = unique_index_booths_event_id_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200


@api_bp.route('/delete', methods=('DELETE',))
def delete_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    try:
        booth_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not booth_id:
        return jsonify(error='missing_id'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_id = cur.execute(f'''
                SELECT event_id
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not event_id:
        return jsonify(error='booth_not_found'), 404
    
    event_id = event_id['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE booths
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (booth_id,))

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {booth_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200

