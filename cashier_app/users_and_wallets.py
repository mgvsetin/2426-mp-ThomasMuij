import os
from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
import json
from psycopg import IntegrityError
import hashlib
from psycopg.errors import ForeignKeyViolation
from psycopg.errors import RaiseException
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.general import convert_uuids_to_str
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price, image_extension_is_allowed, verify_image_file_get_info, save_unique_stream, convert_image_paths_from_relative
from cashier_app.utils.employees_users import is_manager, validate_email, validate_first_or_last_name, validate_phone_number, format_valid_phone_number, add_more_phone_number_info, validate_other_identifier
from cashier_app.utils.products import convert_image_paths_from_relative
from cashier_app.errors import NoRowsAffectedError, MultipleRowsAffectedError, InsufficientBalanceError, UnexpectedError, IdempotencyKeyDataConflict
from cashier_app.utils.transactions import make_transaction
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement


api_bp = Blueprint('users_api', __name__, url_prefix='/api/users')


@api_bp.route('')
def get_users():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        if selected_event is None:
            return jsonify(error='no_selected_event'), 400

        if selected_booth is None:
            return jsonify(error='no_selected_booth'), 400
        
        if selected_booth['booth_type'] != 'cashier':
            return jsonify(error='invalid_booth_type'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            users = cur.execute(
                '''
                SELECT id, first_name, last_name, email, phone_number, other_identifier
                FROM users
                WHERE deleted_at IS NULL
                ORDER BY created_at''',
                ).fetchall()
            
    add_more_phone_number_info(users)
    
    return jsonify(users=users), 200


@api_bp.route('/create', methods=('POST',))
def add_user():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)
                ).fetchone()
                
        if not is_any_manager:
            if selected_event is None:
                return jsonify(error='no_selected_event'), 400

            if selected_booth is None:
                return jsonify(error='no_selected_booth'), 400
            
            if selected_booth['booth_type'] != 'cashier':
                return jsonify(error='invalid_booth_type'), 400
    
    first_name = request.form.get('first-name', '').strip().capitalize()
    last_name = request.form.get('last-name', '').strip().capitalize()
    email = request.form.get('email', '').strip().lower()
    country_code = request.form.get('phone-number-country-code', '').strip()
    phone_number = request.form.get('phone-number', '').strip()
    other_identifier = request.form.get('other-identifier', '').strip()
    
    params = {}

    if not first_name:
        return jsonify(error='missing_first_name'), 400
    
    ok, errors = validate_first_or_last_name(first_name)
    if not ok:
        return jsonify(error=errors[0], detail='first_name_error'), 400
    params['first_name'] = first_name
    
    if not last_name:
        return jsonify(error='missing_last_name'), 400

    ok, errors = validate_first_or_last_name(last_name)
    if not ok:
        return jsonify(error=errors[0], detail='last_name_error'), 400
    params['last_name'] = last_name

    if email:    
        ok, errors = validate_email(email)
        if not ok:
            return jsonify(error=errors[0]), 400
        params['email'] = email

    if phone_number:
        if not country_code:
            return jsonify(error='missing_country_code'), 400
        
        phone_number = f'{country_code}{phone_number}'

        if not validate_phone_number(phone_number):
            return jsonify(error='invalid_phone_number'), 400
        params['phone_number'] = format_valid_phone_number(phone_number)['e164']

    if other_identifier:    
        ok, errors = validate_other_identifier(other_identifier)
        if not ok:
            return jsonify(error=errors[0]), 400
        params['other_identifier'] = other_identifier

    if not (params.get('email') or params.get('phone_number') or params.get('other_identifier')):
        return jsonify(error='at_least_one_of_email_phone_number_other_identifier_is_required'), 400
    
    sql, query_params = build_insert_statement('users', params, returning=['id'])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                user_id = cur.execute(sql, query_params).fetchone()['id']
    except IntegrityError as e:
        constraint = None
        try:
            constraint = getattr(e, 'diag', None) and e.diag.constraint_name
        except Exception:
            constraint = None

        if constraint == 'unique_index_users_names_email_phone_identifier':
            return jsonify(error='user_identifier_taken'), 409
        if constraint == 'unique_index_users_email_active':
            return jsonify(error='user_email_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(user_id=user_id), 200


@api_bp.route('/edit', methods=('POST',))
def edit_user():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        if selected_event is None:
            return jsonify(error='no_selected_event'), 400

        if selected_booth is None:
            return jsonify(error='no_selected_booth'), 400
        
        if selected_booth['booth_type'] != 'cashier':
            return jsonify(error='invalid_booth_type'), 400
        
    try:
        user_id = UUID(request.form.get('user-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400
    
    if not user_id:
        return jsonify(error='missing_user_id'), 400
    
    first_name = request.form.get('first-name', '').strip().capitalize()
    last_name = request.form.get('last-name', '').strip().capitalize()
    email = request.form.get('email', '').strip().lower()
    country_code = request.form.get('phone-number-country-code', '').strip()
    phone_number = request.form.get('phone-number', '').strip()
    other_identifier = request.form.get('other-identifier', '').strip()
    
    params = {}

    if not first_name:
        return jsonify(error='missing_first_name'), 400
    
    ok, errors = validate_first_or_last_name(first_name)
    if not ok:
        return jsonify(error=errors[0], detail='first_name_error'), 400
    params['first_name'] = first_name
    
    if not last_name:
        return jsonify(error='missing_last_name'), 400

    ok, errors = validate_first_or_last_name(last_name)
    if not ok:
        return jsonify(error=errors[0], detail='last_name_error'), 400
    params['last_name'] = last_name

    params['email'] = None
    if email:
        ok, errors = validate_email(email)
        if not ok:
            return jsonify(error=errors[0]), 400
        params['email'] = email

    params['phone_number'] = None
    if phone_number:
        if not country_code:
            return jsonify(error='missing_country_code'), 400
        
        phone_number = f'{country_code}{phone_number}'

        if not validate_phone_number(phone_number):
            return jsonify(error='invalid_phone_number'), 400
        params['phone_number'] = format_valid_phone_number(phone_number)['e164']

    params['other_identifier'] = None
    if other_identifier:    
        ok, errors = validate_other_identifier(other_identifier)
        if not ok:
            return jsonify(error=errors[0]), 400
        params['other_identifier'] = other_identifier

    if not (params.get('email') or params.get('phone_number') or params.get('other_identifier')):
        return jsonify(error='at_least_one_of_email_phone_number_other_identifier_is_required'), 400
    
    sql, query_params = build_update_statement('users', params, user_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, query_params)

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()
                
                #### delete wallets?

    except IntegrityError as e:
        constraint = None
        try:
            constraint = getattr(e, 'diag', None) and e.diag.constraint_name
        except Exception:
            constraint = None

        if constraint == 'unique_index_users_names_email_phone_identifier':
            return jsonify(error='user_identifier_taken'), 409
        if constraint == 'unique_index_users_email_active':
            return jsonify(error='user_email_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for user id %s', user_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='user_not_found'), 404

    return jsonify(), 200


@api_bp.route('/delete', methods=('DELETE',))
def delete_user():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        if selected_event is None:
            return jsonify(error='no_selected_event'), 400

        if selected_booth is None:
            return jsonify(error='no_selected_booth'), 400
        
        if selected_booth['booth_type'] != 'cashier':
            return jsonify(error='invalid_booth_type'), 400
        
    try:
        user_id = UUID(request.form.get('user-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400
    
    if not user_id:
        return jsonify(error='missing_user_id'), 400

    sql, query_params = build_delete_statement('users', user_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, query_params)
                
                # wallets od user se smažou sami pomocí triggeru
                
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for user id %s', user_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='user_not_found'), 404

    return jsonify(), 200


@api_bp.route('/deleted')
def get_deleted_users():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)
                ).fetchone()

        if not is_any_manager:
            selected_event = load_selected_event()
            selected_booth = load_selected_booth()

            if selected_event is None:
                return jsonify(error='no_selected_event'), 400

            if selected_booth is None:
                return jsonify(error='no_selected_booth'), 400

            if selected_booth['booth_type'] != 'cashier':
                return jsonify(error='invalid_booth_type'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            users = cur.execute(
                '''
                SELECT id, first_name, last_name, email, phone_number, other_identifier, deleted_at
                FROM users
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC''',
            ).fetchall()

    add_more_phone_number_info(users)

    return jsonify(users=users), 200


@api_bp.route('/restore', methods=('POST',))
def restore_user():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)
                ).fetchone()

        if not is_any_manager:
            selected_event = load_selected_event()
            selected_booth = load_selected_booth()

            if selected_event is None:
                return jsonify(error='no_selected_event'), 400

            if selected_booth is None:
                return jsonify(error='no_selected_booth'), 400

            if selected_booth['booth_type'] != 'cashier':
                return jsonify(error='invalid_booth_type'), 400

    try:
        user_id = UUID(request.form.get('user-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400

    force = request.form.get('force') == 'true'

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                user = cur.execute(
                    '''SELECT deleted_at, first_name, last_name, email, phone_number, other_identifier
                    FROM users WHERE id = %s AND deleted_at IS NOT NULL''',
                    (user_id,)
                ).fetchone()

                if user is None:
                    return jsonify(error='user_not_found'), 404

                user_deleted_at = user['deleted_at']

                if force:
                    email = user['email']
                    first_name = user['first_name']
                    last_name = user['last_name']
                    phone_number = user['phone_number']
                    other_identifier = user['other_identifier']

                    # fix email uniqueness conflict
                    if email:
                        existing = cur.execute(
                            'SELECT 1 FROM users WHERE email = %s AND deleted_at IS NULL',
                            (email,)
                        ).fetchone()
                        if existing:
                            base, domain = email.rsplit('@', 1)
                            suffix = 1
                            new_email = f"{base}_{suffix}@{domain}"
                            while cur.execute(
                                'SELECT 1 FROM users WHERE email = %s AND deleted_at IS NULL',
                                (new_email,)
                            ).fetchone():
                                suffix += 1
                                new_email = f"{base}_{suffix}@{domain}"
                            cur.execute('UPDATE users SET email = %s WHERE id = %s', (new_email, user_id))
                            email = new_email

                    # fix composite index conflict (names + email + phone + identifier)
                    existing_composite = cur.execute(
                        '''
                        SELECT 1 FROM users
                        WHERE lower(first_name) = lower(%s)
                          AND lower(last_name) = lower(%s)
                          AND COALESCE(NULLIF(lower(email), ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(lower(%s), ''), '<<__NULL___2025__>>')
                          AND COALESCE(NULLIF(phone_number, ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(%s, ''), '<<__NULL___2025__>>')
                          AND COALESCE(NULLIF(lower(other_identifier), ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(lower(%s), ''), '<<__NULL___2025__>>')
                          AND deleted_at IS NULL
                        ''',
                        (first_name, last_name, email, phone_number, other_identifier)
                    ).fetchone()

                    if existing_composite:
                        base_identifier = other_identifier or ''
                        suffix = 1
                        new_identifier = f"{base_identifier}_{suffix}"
                        while cur.execute(
                            '''
                            SELECT 1 FROM users
                            WHERE lower(first_name) = lower(%s)
                              AND lower(last_name) = lower(%s)
                              AND COALESCE(NULLIF(lower(email), ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(lower(%s), ''), '<<__NULL___2025__>>')
                              AND COALESCE(NULLIF(phone_number, ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(%s, ''), '<<__NULL___2025__>>')
                              AND COALESCE(NULLIF(lower(other_identifier), ''), '<<__NULL___2025__>>') = COALESCE(NULLIF(lower(%s), ''), '<<__NULL___2025__>>')
                              AND deleted_at IS NULL
                            ''',
                            (first_name, last_name, email, phone_number, new_identifier)
                        ).fetchone():
                            suffix += 1
                            new_identifier = f"{base_identifier}_{suffix}"
                        cur.execute('UPDATE users SET other_identifier = %s WHERE id = %s', (new_identifier, user_id))

                    # fix wallet tag_id conflicts
                    wallets_to_restore = cur.execute(
                        'SELECT id, event_id, tag_id FROM wallets WHERE owner_id = %s AND deleted_at = %s',
                        (user_id, user_deleted_at)
                    ).fetchall()

                    for wallet in wallets_to_restore:
                        existing_tag = cur.execute(
                            'SELECT 1 FROM wallets WHERE event_id = %s AND tag_id = %s AND deleted_at IS NULL',
                            (wallet['event_id'], wallet['tag_id'])
                        ).fetchone()
                        if existing_tag:
                            base_tag = wallet['tag_id']
                            suffix = 1
                            new_tag = f"{base_tag}_{suffix}"
                            while cur.execute(
                                'SELECT 1 FROM wallets WHERE event_id = %s AND tag_id = %s AND deleted_at IS NULL',
                                (wallet['event_id'], new_tag)
                            ).fetchone():
                                suffix += 1
                                new_tag = f"{base_tag}_{suffix}"
                            cur.execute('UPDATE wallets SET tag_id = %s WHERE id = %s', (new_tag, wallet['id']))

                cur.execute(
                    'UPDATE users SET deleted_at = NULL WHERE id = %s AND deleted_at IS NOT NULL',
                    (user_id,)
                )

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                cur.execute(
                    'UPDATE wallets SET deleted_at = NULL WHERE owner_id = %s AND deleted_at = %s',
                    (user_id, user_deleted_at)
                )
    except IntegrityError as e:
        constraint = None
        try:
            constraint = getattr(e, 'diag', None) and e.diag.constraint_name
        except Exception:
            constraint = None

        if constraint == 'unique_index_users_names_email_phone_identifier':
            return jsonify(error='user_identifier_taken'), 409
        if constraint == 'unique_index_users_email_active':
            return jsonify(error='user_email_taken'), 409
        if constraint == 'unique_index_event_tag_id_active':
            return jsonify(error='tag_id_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows restored for user id %s', user_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='user_not_found'), 404

    return jsonify(), 200


api_wallets_bp = Blueprint('wallets', __name__, url_prefix='/wallets')
api_bp.register_blueprint(api_wallets_bp)


@api_wallets_bp.route('/create', methods=('POST',))
def add_wallet():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if selected_event is None:
        return jsonify(error='no_selected_event'), 400

    if selected_booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    if selected_booth['booth_type'] != 'cashier':
        return jsonify(error='invalid_booth_type'), 400
    

    try:
        owner_id = UUID(request.form.get('user-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400
    
    if not owner_id:
        return jsonify(error='missing_user_id'), 400
    
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

    tag_id = request.form.get('tag-id', '').strip()
    change_balance_by = request.form.get('change-balance-by', '')
    new_balance = request.form.get('new-balance', '')

    params = {
        'created_by': logged_employee['id'],
        'event_id': selected_event['id'],
        'owner_id': owner_id
        }

    if not tag_id:
        return jsonify(error='missing_tag_id'), 400
    
    params['tag_id'] = tag_id

    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400 ##### do on frontend errs

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
    
    if new_balance < 0:
        return jsonify(error='wallet_balance_czk_is_not_enough'), 400
    
    if change_balance_by != new_balance:
        return jsonify(error=f"change_balance_by_and_new_balance_do_not_match"), 400

    sql, query_params = build_insert_statement('wallets', params, returning=['id', 'owner_id'])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(sql, query_params).fetchone()

                transaction_params = {
                'tag_id': tag_id,
                'wallet_id': wallet['id'],
                'user_id': wallet['owner_id'],
                'event_id': selected_event['id'],
                'booth_id': selected_booth['id'],
                'transaction_type': 'balance-change',
                'amount_czk': change_balance_by,
                'performed_by': logged_employee['id'],
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
        constraint = None
        try:
            constraint = getattr(e, 'diag', None) and e.diag.constraint_name
        except Exception:
            constraint = None

        if constraint == 'unique_index_event_tag_id_active':
            return jsonify(error='tag_id_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(balance_changed_by=change_balance_by), 200


@api_wallets_bp.route('/return', methods=('POST',))
def return_wallet():
    logged_employee = load_logged_in_employee()
    selected_event = load_selected_event()
    selected_booth = load_selected_booth()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if selected_event is None:
        return jsonify(error='no_selected_event'), 400

    if selected_booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    if selected_booth['booth_type'] != 'cashier':
        return jsonify(error='invalid_booth_type'), 400

    tag_id = request.form.get('tag-id', '').strip()
    
    if not tag_id:
        return jsonify(error='missing_tag_id'), 400
    
    idemp_key = request.headers.get('Idempotency-Key') or request.form.get('idempotency-key')

    if not idemp_key:
        return jsonify(error='missing_idempotency_key'), 400 ##### do on frontend errs

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
                    (tag_id, selected_event['id'])).fetchone()
                
                change_balance_by = -wallet['balance_czk']

                transaction_params = {
                'tag_id': tag_id,
                'wallet_id': wallet['id'],
                'user_id': wallet['owner_id'],
                'event_id': selected_event['id'],
                'booth_id': selected_booth['id'],
                'transaction_type': 'balance-change',
                'amount_czk': change_balance_by,
                'performed_by': logged_employee['id'],
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
                    (tag_id, selected_event['id']))
                
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
