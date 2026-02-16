"""API endpoint pro získání informací o aktuální relaci (session) uživatele."""

from flask import Blueprint, jsonify
from cashier_app.db import get_pool
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee

api_bp = Blueprint('session_api', __name__, url_prefix='/api/session')


@api_bp.route('')
def session_info():
    """Vrátí informace o aktuální relaci: přihlášený zaměstnanec, vybraná akce a stánek."""
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(employee=None, event=None, booth=None), 200

    event = load_selected_event()
    booth = load_selected_booth()
    
    is_manager = False
    if event:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_manager = bool(cur.execute(
                    '''
                    SELECT 1
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s
                    AND booth_id IS NULL''',
                    (employee['id'], event['id'])).fetchone())
    
    if employee:
        employee = {
            'id': employee['id'],
            'username': employee['username'],
            'email': employee['email'],
            'is_admin': employee['is_admin'],
            'is_event_manager': is_manager
        }
    if event:
        event = {
            'id': event['id'],
            'name': event['name']
        }
    if booth:
        booth = {
            'id': booth['id'],
            'name': booth['name'],
            'booth_type': booth['booth_type']
        }
    
    return jsonify(employee=employee, event=event, booth=booth), 200
