from flask import Blueprint, jsonify, url_for, request
from uuid import UUID
from cashier_app.auth import load_logged_in_employee


api_bp = Blueprint('transactions_api', __name__, url_prefix='/api/transactions')


@api_bp.route('/make')
def make_transaction():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400
    
    # tag_id, wallet_id, user_id, event_id, booth_id, transaction_type, amount_czk, balance_before, balance_after, occured_at, performed_by, products_info
    
