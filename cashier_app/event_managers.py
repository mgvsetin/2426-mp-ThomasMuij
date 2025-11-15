from flask import Blueprint, current_app, jsonify, url_for, redirect
from uuid import UUID
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_db
from cashier_app.events_booths import load_selected_event
from cashier_app.utils.employees import is_manager


bp = Blueprint('event_managers', __name__, url_prefix='/events')


@bp.route('/manager/')
def get_events_manager_page():
    employee = load_logged_in_employee()

    if employee is None:
        return redirect(url_for('auth.login'))

    # if not employee['is_admin'] and not is_manager(employee['id'], event_id):
    #     return jsonify(error='insufficient_priviliges'), 403

    return current_app.send_static_file('html/event_managers/events_manager.html')



@bp.route('/<uuid:event_id>/manager/')
def get_event_manager_page(event_id):
    employee = load_logged_in_employee()

    if employee is None:
        return redirect(url_for('auth.login'))

    if not employee['is_admin'] and not is_manager(employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    return current_app.send_static_file('html/event_managers/event_manager.html')
