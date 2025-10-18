from flask import Blueprint, session, jsonify
from cashier_app.db import get_db

bp = Blueprint('session', __name__, url_prefix='/session')

# {
#   "sub": "user-id-uuid",
#   "email": "user@example.com",
#   "is_system_admin": false,
#   "active_event_id": "event-uuid",
#   "role_for_active_event": "cashier",
#   "iat": 169XXX,
#   "exp": 169YYY
# }

@bp.route('/account-info')
def account_info():
    account_id = session.get('account_id')

    if not account_id:
        return {'logged_in': False}
    
    with get_db() as conn:
        with conn.cursor() as cur:
            account: dict = cur.execute(
                '''
                SELECT id, type, username
                WHERE id = %s AND deleted_at IS NULL''',
                (account_id,)).fetchone()
            
    if not account:
        return {'logged_in': False}
    
    return {
        'logged_in': True,
        'account': account
        }


@bp.route('login-error')
def login_error():
    error = session.get('login_error')

    if error:
        return jsonify(True)
    return jsonify(False) # místo None
