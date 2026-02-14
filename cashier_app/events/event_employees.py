from flask import Blueprint, jsonify, url_for, request
from uuid import UUID
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.link_sync import sync_employee_event_booth_roles

api_employees_bp = Blueprint('employees', __name__, url_prefix='/employees')


@api_employees_bp.route('/assign-manager', methods=('POST',))
def assign_manager():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id, is_admin
                FROM employees
                WHERE (username = %s OR email = %s)
                AND deleted_at IS NULL''',
                (username_or_email, username_or_email)).fetchone()

            event = cur.execute(
                '''
                SELECT 1
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()

            if not event:
                return jsonify(error='event_not_found'), 400

            if not employee:
                return jsonify(error='employee_not_found'), 400

            if employee['is_admin']:
                return jsonify(error='can_not_assign_admin'), 400

            changes = []
            changes.extend(sync_employee_event_booth_roles(cur, employee['id'], event_id, [None]))
            save_change(cur, changes, logged_employee['id'])

    return jsonify(), 200


@api_employees_bp.route('/assign-employee', methods=('POST',))
def assign_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400

    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event = cur.execute(
                '''
                SELECT 1
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()

            if not event:
                return jsonify(error='event_not_found'), 400

            for booth_id in booth_ids:
                booth = cur.execute(
                    '''
                    SELECT 1
                    FROM booths
                    WHERE id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL''',
                    (booth_id, event_id)).fetchone()

                if not booth:
                    return jsonify(error='booth_not_found'), 400

            employee = cur.execute(
                '''
                SELECT id, is_admin
                FROM employees
                WHERE (username = %s OR email = %s)
                AND deleted_at IS NULL''',
                (username_or_email, username_or_email)).fetchone()

            if not employee:
                return jsonify(error='employee_not_found'), 400

            if employee['is_admin']:
                return jsonify(error='can_not_assign_admin'), 400

            role_row = cur.execute(
                '''
                SELECT role
                FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s
                AND booth_id IS NULL''',
                (employee['id'], event_id)).fetchone()

            if role_row:
                return jsonify(error='can_not_assign_manager_to_booths'), 400

            changes = []
            changes.extend(sync_employee_event_booth_roles(cur, employee['id'], event_id, booth_ids))
            save_change(cur, changes, logged_employee['id'])

    return jsonify(), 200


@api_employees_bp.route('/unassign', methods=('POST',))
def unassign_employee_or_manager():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    try:
        employee_id = UUID(request.form.get('id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not employee_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            changes = []

            changes.extend(sync_employee_event_booth_roles(cur, employee_id, event_id, []))

            if changes:
                save_change(cur, changes, logged_employee['id'])

    return jsonify(), 200
