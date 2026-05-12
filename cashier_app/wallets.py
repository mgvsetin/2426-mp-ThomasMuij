"""Modul pro správu peněženek.

Obsahuje API endpointy pro vytváření a vracení peněženek.
"""

from flask import Blueprint, current_app, jsonify, request, g
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.auth import require_login
from cashier_app.employee_events_booths import require_cashier_booth_selected
from cashier_app.db import get_pool
from cashier_app.utils.general import get_constraint_name
from cashier_app.errors import NoRowsAffectedError, MultipleRowsAffectedError, InsufficientBalanceError, UnexpectedError, IdempotencyKeyDataConflict
from cashier_app.utils.transactions import make_transaction
from cashier_app.utils.query_builder import build_insert_statement


api_bp = Blueprint('wallets_api', __name__, url_prefix='/api/wallets')


@api_bp.route('/create', methods=('POST',))
@require_login
@require_cashier_booth_selected
def add_wallet():
    owner_id = request.form.get('user-id')

    if not owner_id:
        return jsonify(error='missing_user_id'), 400

    try:
        owner_id = UUID(owner_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400


    tag_id = request.form.get('tag-id', '').strip()
    change_balance_by = request.form.get('change-balance-by', '')
    new_balance = request.form.get('new-balance', '')

    params = {
        'created_by': g.employee['id'],
        'event_id': g.event['id'],
        'owner_id': owner_id
        }

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    params['tag_id'] = tag_id

    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400

    try:
        change_balance_by = float(change_balance_by)
    except (TypeError, ValueError):
        return jsonify(error='change_balance_by_must_be_a_number'), 400

    if not change_balance_by.is_integer():
        return jsonify(error='change_balance_by_must_be_a_whole_number'), 400

    change_balance_by = int(change_balance_by)

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

    new_balance = int(new_balance)

    if new_balance < -1_000_000:
        return jsonify(error=f"new_balance_must_be_more_than_or_equal_to_-1000000"), 400
    if new_balance > 1_000_000:
        return jsonify(error=f"new_balance_must_be_less_than_or_equal_to_1000000"), 400

    if new_balance < 0:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400

    if change_balance_by != new_balance:
        return jsonify(error=f"change_balance_by_and_new_balance_do_not_match"), 400

    sql, query_params = build_insert_statement('wallets', params, returning=['id', 'owner_id'])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                owner = cur.execute(
                '''
                SELECT 1
                FROM users
                WHERE id = %s
                AND deleted_at IS NULL''',
                (owner_id,)).fetchone()

                if not owner:
                    return jsonify(error='owner_not_found'), 400

                wallet = cur.execute(sql, query_params).fetchone()

                transaction_params = {
                'tag_id': tag_id,
                'wallet_id': wallet['id'],
                'user_id': wallet['owner_id'],
                'event_id': g.event['id'],
                'booth_id': g.booth['id'],
                'transaction_type': 'balance-change',
                'amount_czk': change_balance_by,
                'performed_by': g.employee['id'],
                'products_info': [],
                'idempotency_key': idemp_key,
                }

                make_transaction(transaction_params, cur)


    except InsufficientBalanceError:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    except IdempotencyKeyDataConflict:
        return jsonify(error='idempotency_key_data_conflict'), 409
    except UnexpectedError:
        return jsonify(error='unexpected_error'), 500
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_event_tag_id_active':
            return jsonify(error='tag_id_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(balance_changed_by=change_balance_by), 200


@api_bp.route('/return', methods=('POST',))
@require_login
@require_cashier_booth_selected
def return_wallet():
    tag_id = request.form.get('tag-id', '').strip()

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400

    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(
                    '''
                    SELECT id, owner_id, balance_czk
                    FROM wallets
                    WHERE tag_id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL''',
                    (tag_id, g.event['id'])).fetchone()

                if not wallet:
                    return jsonify(error='wallet_not_found'), 404

                change_balance_by = -wallet['balance_czk']

                transaction_params = {
                'tag_id': tag_id,
                'wallet_id': wallet['id'],
                'user_id': wallet['owner_id'],
                'event_id': g.event['id'],
                'booth_id': g.booth['id'],
                'transaction_type': 'balance-change',
                'amount_czk': change_balance_by,
                'performed_by': g.employee['id'],
                'products_info': [],
                'idempotency_key': idemp_key
                }

                make_transaction(transaction_params, cur)

                cur.execute(
                    '''
                    UPDATE wallets
                    SET deleted_at = now()
                    WHERE tag_id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL''',
                    (tag_id, g.event['id']))

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()
    except InsufficientBalanceError:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    except IdempotencyKeyDataConflict:
        return jsonify(error='idempotency_key_data_conflict'), 409
    except UnexpectedError:
        return jsonify(error='unexpected_error'), 500
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for wallet tag id %s', tag_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='wallet_not_found'), 404

    return jsonify(balance_changed_by=change_balance_by), 200
