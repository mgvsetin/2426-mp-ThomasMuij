from flask import Blueprint, jsonify, url_for, request
from uuid import UUID
import json
from psycopg.errors import RaiseException
import hashlib
from psycopg.types.json import Jsonb
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.general import convert_uuids_to_str
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth


api_bp = Blueprint('transactions_api', __name__, url_prefix='/api/transactions')


@api_bp.route('/make-payment', methods=('POST',))
def make_payment():
    logged_employee = load_logged_in_employee()
    event = load_selected_event()
    booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if event is None:
        return jsonify(error='no_selected_event'), 400

    if booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    if booth['booth_type'] != 'seller':
        return jsonify(error='invalid_booth_type'), 400
    
    tag_id = request.form.get('tag-id', '').strip()
    amount_czk = request.form.get('amount-czk', '')
    products_info = request.form.get('products-info', '[]')
    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
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

    if amount_czk < -1_000_000:
        return jsonify(error='amount_czk_must_be_more_than_or_equal_to_-1000000'), 400
    if amount_czk > 1_000_000:
        return jsonify(error='amount_czk_must_be_less_than_or_equal_to_1000000'), 400

    if wallet['balance_czk'] + amount_czk < 0:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    if wallet['balance_czk'] + amount_czk > 1_000_000:
        return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400

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
            
            try:
                UUID(product['id'])
            except (ValueError, TypeError):
                return jsonify(error='invalid_products_info'), 400
            
            total_products_price -= product['price'] * product['quantity']
    except Exception as e:
        return jsonify(error='invalid_products_info'), 400
    
    if total_products_price != amount_czk:
        return jsonify(error='invalid_products_info'), 400
    
    fingerprint_cols = {
        'tag_id': tag_id,
        'wallet_id': wallet['id'],
        'user_id': wallet['owner_id'],
        'event_id': event['id'],
        'booth_id': booth['id'],
        'transaction_type': 'payment',
        'amount_czk': amount_czk,
        'performed_by': logged_employee['id'],
        'products_info': products_info
    }
    
    fingerprint_source = json.dumps(
        {key: convert_uuids_to_str(value) for key, value in fingerprint_cols.items()},
        separators=(',', ':'), sort_keys=True)
    request_fingerprint = hashlib.sha256(fingerprint_source.encode('utf-8')).hexdigest()
    
    
    params = {
    'tag_id': tag_id,
    'wallet_id': wallet['id'],
    'user_id': wallet['owner_id'],
    'event_id': event['id'],
    'booth_id': booth['id'],
    'transaction_type': 'payment',
    'amount_czk': amount_czk,
    'performed_by': logged_employee['id'],
    'products_info': Jsonb(products_info),
    'idempotency_key': idemp_key,
    'request_fingerprint': request_fingerprint
    }

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])
    
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO transactions
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                    ''',
                    params)
                # wallet se updatuje pomocí trigger v db
                inserted = cur.fetchone()

                if not inserted:                
                    cur.execute(
                        '''
                        SELECT id, request_fingerprint
                        FROM transactions
                        WHERE idempotency_key = %s
                        ''', (idemp_key,))
                    existing = cur.fetchone()

                    if not existing:
                        return jsonify(error='unexpected_error'), 500
                    
                    existing_fingerprint = existing['request_fingerprint']

                    if existing_fingerprint != request_fingerprint:
                        # stejný idempotency key s jinými daty
                        return jsonify(error='idempotency_key_data_conflict'), 409
    except RaiseException as e:
        text = str(e)

        if "insufficient balance" in text:
            return jsonify(error='wallet_balance_czk_is_not_enough'), 400
        else:
            return jsonify(error='unexpected_error'), 500

    return jsonify(), 200


@api_bp.route('/make-balance-change', methods=('POST',))
def make_balance_change():
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
    change_balance_by = request.form.get('change-balance-by', '')
    new_balance = request.form.get('new-balance', '')
    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400 ##### do on frontend errs

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    if booth['booth_type'] != 'cashier':
        return jsonify(error='invalid_booth_type'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
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
        change_balance_by = float(change_balance_by)
    except (TypeError, ValueError):
        return jsonify(error='change_balance_by_must_be_a_number'), 400
    
    if not change_balance_by.is_integer():
        return jsonify(error='change_balance_by_must_be_a_whole_number'), 400

    if change_balance_by < -1_000_000:
        return jsonify(error=f"change_balance_by_must_be_more_than_or_equal_to_-1000000"), 400
    if change_balance_by > 1_000_000:
        return jsonify(error=f"change_balance_by_must_be_less_than_or_equal_to_1000000"), 400
    
    try:
        new_balance = float(new_balance)
    except (TypeError, ValueError):
        return jsonify(error='new_balance_must_be_a_number'), 400
    
    if not new_balance.is_integer():
        return jsonify(error='new_balance_must_be_a_whole_number'), 400
    if new_balance < -1_000_000:
        return jsonify(error=f"new_balance_must_be_more_than_or_equal_to_-1000000"), 400
    if new_balance > 1_000_000:
        return jsonify(error=f"new_balance_must_be_less_than_or_equal_to_1000000"), 400
    
    if wallet['balance_czk'] + change_balance_by != new_balance:
        return jsonify(error='changes_do_not_match_balance_czk'), 400

    if wallet['balance_czk'] + change_balance_by < 0:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    if wallet['balance_czk'] + change_balance_by > 1_000_000:
        return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400

    fingerprint_cols = {
        'tag_id': tag_id,
        'wallet_id': wallet['id'],
        'user_id': wallet['owner_id'],
        'event_id': event['id'],
        'booth_id': booth['id'],
        'transaction_type': 'balance-change',
        'amount_czk': change_balance_by,
        'performed_by': logged_employee['id'],
        'products_info': '[]'
    }
    
    fingerprint_source = json.dumps(
        {key: convert_uuids_to_str(value) for key, value in fingerprint_cols.items()},
        separators=(',', ':'), sort_keys=True)
    request_fingerprint = hashlib.sha256(fingerprint_source.encode('utf-8')).hexdigest()
    
    params = {
    'tag_id': tag_id,
    'wallet_id': wallet['id'],
    'user_id': wallet['owner_id'],
    'event_id': event['id'],
    'booth_id': booth['id'],
    'transaction_type': 'balance-change',
    'amount_czk': change_balance_by,
    'performed_by': logged_employee['id'],
    'idempotency_key': idemp_key,
    'request_fingerprint': request_fingerprint
    }
    
    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])
    
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO transactions
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                    ''',
                    params)
                # wallet se updatuje pomocí trigger v db
                inserted = cur.fetchone()

                if not inserted:                
                    cur.execute(
                        '''
                        SELECT id, request_fingerprint
                        FROM transactions
                        WHERE idempotency_key = %s
                        ''', (idemp_key,))
                    existing = cur.fetchone()

                    if not existing:
                        return jsonify(error='unexpected_error'), 500
                    
                    existing_fingerprint = existing['request_fingerprint']

                    if existing_fingerprint != request_fingerprint:
                        # stejný idempotency key s jinými daty
                        return jsonify(error='idempotency_key_data_conflict'), 409
    except RaiseException as e:
        text = str(e)

        if "insufficient balance" in text:
            return jsonify(error='wallet_balance_czk_is_not_enough'), 400
        else:
            return jsonify(error='unexpected_error'), 500
            
    return jsonify(), 200