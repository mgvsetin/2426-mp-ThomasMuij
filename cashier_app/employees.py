from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_db
from cashier_app.utils.employees import is_manager, validate_username, validate_email, validate_password

bp = Blueprint('employees', __name__, url_prefix='/api/employees')


@bp.route('/')
def get_employees():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401
    
    conn = get_db()

    if not employee['is_admin']:
        event = load_selected_event()

        if not event or not is_manager(employee['id'], event['id']):
            return jsonify(error='admin_or_manager_required'), 403

    with conn.transaction():
        with conn.cursor() as cur:
            employees = cur.execute('''
                SELECT e.id, e.username, e.email, e.is_admin, e.created_by, e.created_at
                FROM employees as e
                WHERE e.deleted_at IS NULL
                ORDER BY created_at''').fetchall()
            
    return jsonify(employees=employees), 200


@bp.route('/create', methods=('POST',))
def add_employee(): 
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    if not logged_employee['is_admin']:
        return jsonify(error='insufficient_priviliges'), 403

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password_raw = request.form.get('password', '')

    if not username:
        return jsonify(error='missing_username'), 400
    
    if not email:
        return jsonify(error='missing_email'), 400
    
    if not password_raw:
        return jsonify(error='missing_password'), 400


    ok, errors = validate_username(username)
    if not ok:
        return jsonify(error=errors[0]), 400

    ok, errors = validate_email(email)
    if not ok:
        return jsonify(error="invalid_email"), 400    

    ok, errors = validate_password(password_raw)
    if not ok:
        return jsonify(error=errors[0]), 400
    
    password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
    password_hash = password_hasher.hash(password_raw)        

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO employees
                    (username, email, password_hash, created_by)
                    VALUES (%s, %s, %s, %s)''',
                    (username, email, password_hash, logged_employee['id']))

    except IntegrityError as e:
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@bp.route('/edit', methods=('POST',))
def edit_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    try:
        edit_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not edit_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != edit_employee_id:
        return jsonify(error='insufficient_priviliges'), 403

    new_username = request.form.get('username', '').strip()
    new_email = request.form.get('email', '').strip().lower()
    new_password_raw = request.form.get('password', '')

    col_updates = []
    params = {'edit_employee_id': edit_employee_id}

    if new_username:
        ok, errors = validate_username(new_username)
        if not ok:
            return jsonify(error=errors[0]), 400
        col_updates.append('username = %(new_username)s')
        params['new_username'] = new_username
    
    if new_email:
        ok, errors = validate_email(new_email)
        if not ok:
            return jsonify(error="invalid_email"), 400
        col_updates.append('email = %(new_email)s')
        params['new_email'] = new_email
        
    if new_password_raw:
        ok, errors = validate_password(new_password_raw)
        if not ok:
            return jsonify(error=errors[0]), 400
        
        password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
        new_password_hash = password_hasher.hash(new_password_raw)

        col_updates.append('password_hash = %(new_password_hash)s')
        params['new_password_hash'] = new_password_hash

        

    if not col_updates:
        return jsonify(error='no_column_updated'), 400

    col_updates_str = ', '.join(col_updates)

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(f'''
                    UPDATE employees
                    SET {col_updates_str}
                    WHERE id = %(edit_employee_id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {edit_employee_id}')
    except IntegrityError as e:
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for employee id %s', edit_employee_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='employee_not_found'), 404

    return jsonify(), 200


@bp.route('/delete', methods=('DELETE',))
def delete_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    try:
        delete_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not delete_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != delete_employee_id:
        return jsonify(error='insufficient_priviliges'), 403

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE employees
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (delete_employee_id,))
                
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {delete_employee_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for employee id %s', delete_employee_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='employee_not_found'), 404

    return jsonify(), 200