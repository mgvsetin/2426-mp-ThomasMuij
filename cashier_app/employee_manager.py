from flask import Blueprint, current_app, jsonify, url_for, redirect
from cashier_app.auth import load_logged_in_employee


bp = Blueprint('user_manager', __name__, url_prefix='/admin/employee_manager')


@bp.route('/')
def get_user_manager_page():
    employee = load_logged_in_employee()

    if employee is None:
        return redirect(url_for('auth.login'))

    if not employee['is_admin']:
        return jsonify(error='admin_required'), 403

    return current_app.send_static_file('html/employee_manager/employee_manager.html')
