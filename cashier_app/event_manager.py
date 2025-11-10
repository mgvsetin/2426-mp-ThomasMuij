from flask import Blueprint, current_app, jsonify, url_for, redirect
from cashier_app.auth import load_logged_in_employee
from cashier_app.events_booths import load_selected_event
from cashier_app.utils.employees import is_manager


bp = Blueprint('event_manager', __name__, url_prefix='/events/event_manager')


@bp.route('/')
def get_event_manager_page():
    employee = load_logged_in_employee()
    event = load_selected_event()

    if employee is None:
        return redirect(url_for('auth.login'))

    if not employee['is_admin'] and not is_manager(employee, event):
        return jsonify(error='insufficient_priviliges'), 403

    return 'a'
    return current_app.send_static_file('html/event_manager/event_manager.html')
