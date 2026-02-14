from flask import Blueprint, jsonify, url_for, request, current_app
from uuid import UUID
import json
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.utils.transactions import make_transaction
from cashier_app.errors import UnexpectedError, InsufficientBalanceError, IdempotencyKeyDataConflict


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

    try:
        amount_czk = float(amount_czk)
    except (TypeError, ValueError):
        return jsonify(error='amount_czk_must_be_a_number'), 400

    if not amount_czk.is_integer():
        return jsonify(error='amount_czk_must_be_a_whole_number'), 400

    amount_czk = int(amount_czk)

    if amount_czk < -1_000_000:
        return jsonify(error='amount_czk_must_be_more_than_or_equal_to_-1000000'), 400
    if amount_czk > 1_000_000:
        return jsonify(error='amount_czk_must_be_less_than_or_equal_to_1000000'), 400

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

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(
                    '''
                    SELECT id, owner_id, balance_czk
                    FROM wallets
                    WHERE tag_id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL
                    FOR UPDATE''',
                    (tag_id, event['id'])).fetchone()

                if not wallet:
                    return jsonify(error='wallet_not_found'), 400

                if wallet['balance_czk'] + amount_czk < 0:
                    return jsonify(error='wallet_balance_czk_is_not_enough'), 400
                if wallet['balance_czk'] + amount_czk > 1_000_000:
                    return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400

                params = {
                    'tag_id': tag_id,
                    'wallet_id': wallet['id'],
                    'user_id': wallet['owner_id'],
                    'event_id': event['id'],
                    'booth_id': booth['id'],
                    'transaction_type': 'payment',
                    'amount_czk': amount_czk,
                    'performed_by': logged_employee['id'],
                    'products_info': products_info,
                    'idempotency_key': idemp_key
                }

                make_transaction(params, cursor=cur)
    except InsufficientBalanceError:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    except IdempotencyKeyDataConflict:
        return jsonify(error='idempotency_key_data_conflict'), 409
    except UnexpectedError:
        return jsonify(error='unexpected_error'), 500

    return jsonify(balance_changed_by=amount_czk), 200


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

    if booth['booth_type'] != 'cashier':
        return jsonify(error='invalid_booth_type'), 400

    tag_id = request.form.get('tag-id', '').strip()
    change_balance_by = request.form.get('change-balance-by', '')
    new_balance = request.form.get('new-balance', '')
    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    try:
        change_balance_by = float(change_balance_by)
    except (TypeError, ValueError):
        return jsonify(error='change_balance_by_must_be_a_number'), 400

    if not change_balance_by.is_integer():
        return jsonify(error='change_balance_by_must_be_a_whole_number'), 400

    change_balance_by = int(change_balance_by)

    if change_balance_by < -1_000_000:
        return jsonify(error='change_balance_by_must_be_more_than_or_equal_to_-1000000'), 400
    if change_balance_by > 1_000_000:
        return jsonify(error='change_balance_by_must_be_less_than_or_equal_to_1000000'), 400

    try:
        new_balance = float(new_balance)
    except (TypeError, ValueError):
        return jsonify(error='new_balance_must_be_a_number'), 400

    if not new_balance.is_integer():
        return jsonify(error='new_balance_must_be_a_whole_number'), 400

    new_balance = int(new_balance)

    if new_balance < -1_000_000:
        return jsonify(error='new_balance_must_be_more_than_or_equal_to_-1000000'), 400
    if new_balance > 1_000_000:
        return jsonify(error='new_balance_must_be_less_than_or_equal_to_1000000'), 400

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(
                    '''
                    SELECT id, owner_id, balance_czk
                    FROM wallets
                    WHERE tag_id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL
                    FOR UPDATE''',
                    (tag_id, event['id'])).fetchone()

                if not wallet:
                    return jsonify(error='wallet_not_found'), 400

                if wallet['balance_czk'] + change_balance_by != new_balance:
                    return jsonify(error='changes_do_not_match_balance_czk'), 400

                if wallet['balance_czk'] + change_balance_by < 0:
                    return jsonify(error='wallet_balance_czk_is_not_enough'), 400
                if wallet['balance_czk'] + change_balance_by > 1_000_000:
                    return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400

                params = {
                    'tag_id': tag_id,
                    'wallet_id': wallet['id'],
                    'user_id': wallet['owner_id'],
                    'event_id': event['id'],
                    'booth_id': booth['id'],
                    'transaction_type': 'balance-change',
                    'amount_czk': change_balance_by,
                    'performed_by': logged_employee['id'],
                    'products_info': [],
                    'idempotency_key': idemp_key
                }

                make_transaction(params, cursor=cur)
    except InsufficientBalanceError:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    except IdempotencyKeyDataConflict:
        return jsonify(error='idempotency_key_data_conflict'), 409
    except UnexpectedError:
        return jsonify(error='unexpected_error'), 500

    return jsonify(balance_changed_by=change_balance_by), 200


def _find_last_refundable_payment(cur, wallet_id, booth_id, event_id, time_limit_minutes):
    return cur.execute(
        '''
        SELECT t.id, t.amount_czk, t.products_info, t.occurred_at
        FROM transactions t
        WHERE t.wallet_id = %s
        AND t.booth_id = %s
        AND t.event_id = %s
        AND t.transaction_type = 'payment'
        AND t.occurred_at > now() - make_interval(mins := %s)
        AND NOT EXISTS (
            SELECT 1 FROM transactions r
            WHERE r.refunded_transaction_id = t.id
        )
        ORDER BY t.occurred_at DESC
        LIMIT 1''',
        (wallet_id, booth_id, event_id, time_limit_minutes)).fetchone()


@api_bp.route('/last-refundable', methods=('GET',))
def get_last_refundable():
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

    tag_id = request.args.get('tag-id', '').strip()

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

            time_limit = current_app.config.get('REFUND_TIME_LIMIT_MINUTES', 5)
            payment = _find_last_refundable_payment(cur, wallet['id'], booth['id'], event['id'], time_limit)

    if not payment:
        return jsonify(error='no_refundable_transaction'), 400

    refund_amount = -payment['amount_czk']

    return jsonify(
        refund_amount=refund_amount,
        products_info=payment['products_info'],
        occurred_at=payment['occurred_at'].isoformat()
    ), 200


@api_bp.route('/make-refund', methods=('POST',))
def make_refund():
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
    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(
                    '''
                    SELECT id, owner_id, balance_czk
                    FROM wallets
                    WHERE tag_id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL
                    FOR UPDATE''',
                    (tag_id, event['id'])).fetchone()

                if not wallet:
                    return jsonify(error='wallet_not_found'), 400

                time_limit = current_app.config.get('REFUND_TIME_LIMIT_MINUTES', 5)
                payment = _find_last_refundable_payment(cur, wallet['id'], booth['id'], event['id'], time_limit)

                if not payment:
                    return jsonify(error='no_refundable_transaction'), 400

                refund_amount = -payment['amount_czk']

                if wallet['balance_czk'] + refund_amount > 1_000_000:
                    return jsonify(error='resulting_wallet_balance_czk_is_too_high'), 400

                params = {
                    'tag_id': tag_id,
                    'wallet_id': wallet['id'],
                    'user_id': wallet['owner_id'],
                    'event_id': event['id'],
                    'booth_id': booth['id'],
                    'transaction_type': 'refund',
                    'amount_czk': refund_amount,
                    'performed_by': logged_employee['id'],
                    'products_info': payment['products_info'],
                    'idempotency_key': idemp_key,
                    'refunded_transaction_id': payment['id']
                }

                make_transaction(params, cursor=cur)
    except InsufficientBalanceError:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    except IdempotencyKeyDataConflict:
        return jsonify(error='idempotency_key_data_conflict'), 409
    except UnexpectedError:
        return jsonify(error='unexpected_error'), 500

    return jsonify(
        balance_changed_by=refund_amount,
        refunded_products=payment['products_info'],
        refunded_amount=refund_amount
    ), 200
