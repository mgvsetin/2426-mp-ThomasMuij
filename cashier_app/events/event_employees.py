"""Modul pro správu zaměstnanců a manažerů přiřazených k událostem."""

from flask import Blueprint, g, jsonify, url_for, request
from uuid import UUID
from cashier_app.auth import load_logged_in_employee, require_login
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.link_sync import sync_employee_event_booth_roles

api_employees_bp = Blueprint('employees', __name__, url_prefix='/employees')


@api_employees_bp.route('/assign-manager', methods=('POST',))
@require_login
def assign_manager():
    """Přiřadí zaměstnance jako manažera k dané události.

    Ověří přihlášení, oprávnění a existenci události i zaměstnance.
    Administrátor nemůže být přiřazen jako manažer.
    Synchronizuje role zaměstnance pro danou událost a uloží změnu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    event_id = request.form.get('event-id')

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id, is_admin
                FROM employees
                WHERE (LOWER(username) = %s OR LOWER(email) = %s)
                AND deleted_at IS NULL''',
                (username_or_email.lower(), username_or_email.lower())).fetchone()

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
            save_change(cur, changes, g.employee['id'])

    return jsonify(), 200


@api_employees_bp.route('/assign-employee', methods=('POST',))
@require_login
def assign_employee():
    """Přiřadí zaměstnance ke konkrétním stánkům v rámci události.

    Ověří přihlášení, oprávnění, existenci události, stánků i zaměstnance.
    Administrátor nemůže být přiřazen ke stánkům.
    Manažer události nemůže být přiřazen ke stánkům.
    Synchronizuje role zaměstnance pro dané stánky a uloží změnu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    event_id = request.form.get('event-id')

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400

    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400

    if not booth_ids:
        return jsonify(error='missing_booths'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
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
                WHERE (LOWER(username) = %s OR LOWER(email) = %s)
                AND deleted_at IS NULL''',
                (username_or_email.lower(), username_or_email.lower())).fetchone()

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
            save_change(cur, changes, g.employee['id'])

    return jsonify(), 200


@api_employees_bp.route('/unassign', methods=('POST',))
@require_login
def unassign_employee_or_manager():
    """Odebere zaměstnance nebo manažera z dané události.

    Ověří přihlášení, oprávnění a platnost identifikátorů události a zaměstnance.
    Synchronizuje role zaměstnance s prázdným seznamem stánků (odebrání všech rolí)
    a uloží změnu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    event_id = request.form.get('event-id')

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403
    
    employee_id = request.form.get('id')

    if not employee_id:
        return jsonify(error='missing_id'), 400

    try:
        employee_id = UUID(employee_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400    

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            changes = []

            changes.extend(sync_employee_event_booth_roles(cur, employee_id, event_id, []))

            if changes:
                save_change(cur, changes, g.employee['id'])

    return jsonify(), 200
