from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.employee_events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager, validate_username, validate_email, validate_password
from cashier_app.errors import NoRowsAffectedError, MultipleRowsAffectedError, CanNotDeleteLastAdminError

bp = Blueprint('employees', __name__, url_prefix='/employees')



@bp.route('/manager')
def get_employees_manager_page():
    # employee = load_logged_in_employee()

    # if employee is None:
    #     return redirect(url_for('auth.login'))

    # if not employee['is_admin']:
    #     return jsonify(error='admin_required'), 403
    return current_app.send_static_file('html/employee_managers/employees_manager.html')


api_bp = Blueprint('employees_api', __name__, url_prefix='/api/employees')


@api_bp.route('')
def get_employees():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not employee['is_admin']:
        event = load_selected_event()

        if not event or not is_manager(employee['id'], event['id']):
            return jsonify(error='admin_or_manager_required'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employees = cur.execute(
                '''
                SELECT e.id, e.username, e.email, e.is_admin, e.created_by, e.created_at
                FROM employees as e
                WHERE e.deleted_at IS NULL
                ORDER BY created_at''').fetchall()
            
    return jsonify(employees=employees), 200


@api_bp.route('/create', methods=('POST',))
def add_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        return jsonify(error='insufficient_privileges'), 403

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password_raw = request.form.get('password', '')
    is_admin = request.form.get('is-admin', False)

    if is_admin in ['true', 'on', 'yes']:
        is_admin = True
    else:
        is_admin = False

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

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    INSERT INTO employees
                    (username, email, password_hash, is_admin, created_by)
                    VALUES (%s, %s, %s, %s, %s)''',
                    (username, email, password_hash, is_admin, logged_employee['id']))                    

    except IntegrityError as e:
        # username už existuje: detail obsahuje unique_index_employees_username_active
        # email už existuje: detail obsahuje unique_index_employees_email_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_bp.route('/edit', methods=('POST',))
def edit_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        edit_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not edit_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != edit_employee_id:
        return jsonify(error='insufficient_privileges'), 403

    new_username = request.form.get('username', '').strip()
    new_email = request.form.get('email', '').strip().lower()
    new_password_raw = request.form.get('password', '')
    is_admin = request.form.get('is-admin', False)

    if is_admin in ['true', 'on', 'yes']:
        is_admin = True
    else:
        is_admin = False

    params = {'is_admin': is_admin}

    if not new_username:
        return jsonify(error='missing_username'), 400

    ok, errors = validate_username(new_username)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['username'] = new_username

    if not new_email:
        return jsonify(error='missing_email'), 400
    
    ok, errors = validate_email(new_email)
    if not ok:
        return jsonify(error="invalid_email"), 400
    params['email'] = new_email
        
    if new_password_raw:
        ok, errors = validate_password(new_password_raw)
        if not ok:
            return jsonify(error=errors[0]), 400
        
        password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
        new_password_hash = password_hasher.hash(new_password_raw)

        params['password_hash'] = new_password_hash

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = edit_employee_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                # if is_admin:
                #     cur.execute(
                #         '''
                #         DELETE FROM employee_event_booth_roles
                #         WHERE employee_id = %s
                #         ''',
                #         (edit_employee_id,))

                cur.execute(
                    f'''
                    UPDATE employees
                    SET {col_updates_str}
                    WHERE id = %(id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()
                
                an_admin_exists = cur.execute(
                        '''
                        SELECT 1
                        FROM employees
                        WHERE is_admin IS TRUE
                        AND deleted_at IS NULL''').fetchone()
                    
                if not an_admin_exists:
                    raise CanNotDeleteLastAdminError()
    
    except IntegrityError as e:
        # username už existuje: detail obsahuje unique_index_employees_username_active
        # email už existuje: detail obsahuje unique_index_employees_email_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for employee id %s', edit_employee_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='employee_not_found'), 404
    except CanNotDeleteLastAdminError:
        return jsonify(error='can_not_delete_last_admin'), 400

    return jsonify(), 200


@api_bp.route('/delete', methods=('DELETE',))
def delete_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        delete_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not delete_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != delete_employee_id:
        return jsonify(error='insufficient_privileges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    UPDATE employees
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (delete_employee_id,))
                
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()
                
                an_admin_exists = cur.execute(
                    '''
                    SELECT 1
                    FROM employees
                    WHERE is_admin IS TRUE
                    AND deleted_at IS NULL''').fetchone()
                
                if not an_admin_exists:
                    raise CanNotDeleteLastAdminError()
                

    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for employee id %s', delete_employee_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='employee_not_found'), 404
    except CanNotDeleteLastAdminError:
        return jsonify(error='can_not_delete_last_admin'), 400

    return jsonify(), 200