from flask import Blueprint, current_app, jsonify, url_for, session, request
from cashier_app.events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_db
from cashier_app.utils.employees import is_manager

bp = Blueprint('employees', __name__, url_prefix='/api/employees')


@bp.route('/')
def get_employees():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401
    
    conn = get_db()

    if not employee['is_admin']:
        event = load_selected_event()

        if event and not is_manager(employee, event):
            return jsonify(error='admin_or_manager_required'), 403

    with conn.transaction():
        with conn.cursor() as cur:
            employees = cur.execute('''
                SELECT e.id, e.username, e.email, e.is_admin, e.created_by, e.created_at
                FROM employees as e
                WHERE e.deleted_at IS NULL''').fetchall()
            
    return jsonify(employees=employees), 200


@bp.route('/edit', methods=('POST',))
def edit_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    edit_employee_id = request.form.get('id')

    if not logged_employee['is_admin'] or logged_employee['id'] != edit_employee_id:
        return jsonify(error='insufficient_priviliges'), 403

    new_username = request.form.get('username', '').strip()
    new_email = request.form.get('email', '').strip()
    new_password = request.form.get('password', '')

    sql = 'UPDATE employees SET'

    # do the validation for all of these, funcs in utils employee
    column_set = False
    if new_username:
        sql += f' username = %s' #{new_username}
        column_set = True
    if new_email:
        if column_set:
            sql += ','
        sql += f' email = %s' #{new_email}
        column_set = True
    if new_password:
        if column_set:
            sql += ','
        sql += f' password_hash = %s' #new_password_hash
        column_set = True

    if not column_set:
        return jsonify()

    sql += f'WHERE id = %s' #edit_employee_id

    conn = get_db()

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(sql)

