from flask import Blueprint, session, jsonify
from cashier_app.db import get_db
from cashier_app.events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee

bp = Blueprint('session', __name__, url_prefix='/api/session')

# {
#   "sub": "user-id-uuid",
#   "email": "user@example.com",
#   "is_system_admin": false,
#   "active_event_id": "event-uuid",
#   "role_for_active_event": "cashier",
#   "iat": 169XXX,
#   "exp": 169YYY
# }

@bp.route('/')
def account_info():
    employee = load_logged_in_employee()
    event = load_selected_event()
    booth = load_selected_booth()
    
    if employee:
        employee = {
            'id': employee['id'],
            'username': employee['username'],
            'email': employee['email'],
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