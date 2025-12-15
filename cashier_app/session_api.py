from flask import Blueprint, session, jsonify
from cashier_app.db import get_pool
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee

api_bp = Blueprint('session_api', __name__, url_prefix='/api/session')

# {
#   "sub": "user-id-uuid",
#   "email": "user@example.com",
#   "is_system_admin": false,
#   "active_event_id": "event-uuid",
#   "role_for_active_event": "cashier",
#   "iat": 169XXX,
#   "exp": 169YYY
# }

@api_bp.route('') #/ why does it work with a slash (different from others)??
def session_info():
    employee = load_logged_in_employee()
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


# @bp.route('/booth-is-registered')
# def booth_is_registered():
#     event = load_selected_event()
#     booth = load_selected_booth()

#     # return jsonify(event and booth and event['id'] == booth['event_id']), 200
#     # nejde, protože to může být None
#     if event and booth and event['id'] == booth['event_id']:
#         return jsonify(True), 200
#     else:
#         return jsonify(False), 200