from flask import Blueprint, current_app, jsonify, request, url_for, render_template
from argon2 import PasswordHasher
from cashier_app.auth import load_logged_in_employee, employee_password_is_correct
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import validate_username, validate_email, validate_new_password
from psycopg import IntegrityError
from cashier_app.errors import MultipleRowsAffectedError, NoRowsAffectedError
from cashier_app.utils.query_builder import build_update_statement
from cashier_app.utils.general import get_constraint_name


bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('')
def get_settings_page():
    return render_template('settings/settings.html')


api_bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')


@api_bp.route('/profile')
def get_profile():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    return jsonify(employee={
        'id': logged_employee['id'],
        'username': logged_employee['username'],
        'email': logged_employee['email'],
        'is_admin': logged_employee['is_admin']
    }), 200


@api_bp.route('/update-profile', methods=('POST',))
def update_profile():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    current_password = request.form.get('current-password', '')
    # new_username = request.form.get('username', '').strip()
    # new_email = request.form.get('email', '').strip().lower()

    new_password = request.form.get('new-password', '')
    confirm_password = request.form.get('confirm-password', '')

    if not current_password:
        return jsonify(error='missing_current_password'), 400

    # if not (new_username or new_email or new_password or confirm_password):
    #     return jsonify(error='nothing_to_update'), 400
    if not (new_password or confirm_password):
        return jsonify(error='nothing_to_update'), 400
    

    if not employee_password_is_correct(logged_employee['id'], current_password):
        return jsonify(error='invalid_current_password'), 400
    
    params = {}

    # if new_username:
    #     ok, errors = validate_username(new_username)
    #     if not ok:
    #         return jsonify(error=errors[0]), 400
    #     params['username'] = new_username

    # if new_email:
    #     ok, errors = validate_email(new_email)
    #     if not ok:
    #         return jsonify(error='invalid_email'), 400
    #     params['email'] = new_email


    if new_password or confirm_password:
        if not new_password:
            return jsonify(error='missing_new_password'), 400
        
        if new_password != confirm_password:
            return jsonify(error='passwords_do_not_match'), 400

        ok, errors = validate_new_password(new_password)
        if not ok:
            return jsonify(error=errors[0]), 400
        
        password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])

        new_hash = password_hasher.hash(new_password)

        params['password_hash'] = new_hash
    
    sql, query_params = build_update_statement('employees', params, logged_employee['id'], include_deleted_at_is_null=True)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, query_params)

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for employee id %s', logged_employee['id'])
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='employee_not_found'), 404
    # except IntegrityError as e:
    #     constraint = get_constraint_name(e)

    #     if constraint == 'unique_index_employees_username_active':
    #         return jsonify(error='username_taken'), 409
    #     if constraint == 'unique_index_employees_email_active':
    #         return jsonify(error='email_taken'), 409

    #     return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200
