from flask import Blueprint, current_app, jsonify, url_for
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
