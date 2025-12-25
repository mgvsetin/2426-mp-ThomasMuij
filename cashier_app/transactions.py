from flask import Blueprint, jsonify, url_for, request
from uuid import UUID
import json
from psycopg.types.json import Jsonb
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth


api_bp = Blueprint('transactions_api', __name__, url_prefix='/api/transactions')


@api_bp.route('/make', methods=('POST',))
def make_transaction():
    logged_employee = load_logged_in_employee()
    event = load_selected_event()
    booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if event is None:
        return jsonify(error='no_selected_event'), 400

    if booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    tag_id = request.form.get('tag-id', '').strip()
    transaction_type = request.form.get('transaction-type', '').strip().lower()
    amount_czk = request.form.get('amount-czk', '')
    products_info = request.form.get('products-info', '[]')

    with get_pool().connection() as conn:
        with conn.cursor() as cur:                            
            if ((booth['booth_type'] == 'seller' and transaction_type not in ['payment']) 
                or (booth['booth_type'] == 'cashier' and transaction_type not in ['deposit', 'withdrawal'])):
                return jsonify(error='invalid_booth_type_for_transaction_type'), 400
            
            wallet = cur.execute(
                '''
                SELECT id, owner_id, balance_czk
                FROM wallets
                WHERE tag_id = %s
                AND event_id = %s
                AND deleted_at IS NULL''',
                (tag_id, event['id'])).fetchone()
            
            if not wallet:
                return jsonify(error='wallet_not_found'), 400
            
        try:
            amount_czk = float(amount_czk)
        except (TypeError, ValueError):
            return jsonify(error='amount_czk_must_be_a_number'), 400
        
        if not amount_czk.is_integer():
            return jsonify(error='amount_czk_must_be_a_whole_number'), 400

        if amount_czk < -2_147_483_647:
            return jsonify(error='amount_czk_must_be_more_than_or_equal_to_-2147483647'), 400
        if amount_czk > 2_147_483_647:
            return jsonify(error='amount_czk_must_be_less_than_or_equal_to_2147483647'), 400

        if wallet['balance_czk'] + amount_czk < 0:
            return jsonify(error='wallet_balance_czk_is_not_enough'), 400
        if wallet['balance_czk'] + amount_czk > 2_147_483_647:
            return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400
        
        if transaction_type not in ('deposit', 'payment', 'withdrawal'):
            return jsonify(error='invalid_transaction_type'), 400
            
        if ((transaction_type in ('deposit',) and amount_czk < 0)
            or (transaction_type in ('payment','withdrawal') and amount_czk > 0)):
            return jsonify(error='invalid_transaction_type_for_amount_czk'), 400
        
        try:
            products_info = json.loads(products_info)
            total_products_price = 0
            for product in products_info:
                if product['quantity'] < 1:
                    return jsonify(error='invalid_products_info'), 400
                
                ok, errors = validate_product_or_category_name(product['name'])
                if not ok:
                    return jsonify(error='invalid_products_info'), 400
                
                ok, errors = validate_product_price(product['price'])
                if not ok:
                    return jsonify(error='invalid_products_info'), 400
                
                total_products_price -= product['price'] * product['quantity']
        except Exception as e:
            return jsonify(error='invalid_products_info'), 400
        
        if total_products_price != amount_czk:
            return jsonify(error='invalid_products_info'), 400
        
        params = {
        'tag_id': tag_id,
        'wallet_id': wallet['id'],
        'user_id': wallet['owner_id'],
        'event_id': event['id'],
        'booth_id': booth['id'],
        'transaction_type': transaction_type,
        'amount_czk': amount_czk,
        'performed_by': logged_employee['id'],
        'products_info': Jsonb(products_info)
        }
        
        cols_str = ', '.join(params.keys())
        col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])
        
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO transactions
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    params)
                # wallet se updatuje pomocí trigger v db

        return jsonify(), 200

    
