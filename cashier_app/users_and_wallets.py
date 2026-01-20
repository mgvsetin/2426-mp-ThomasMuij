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
from cashier_app.utils.employees_users import is_manager, validate_email, validate_first_or_last_name, validate_phone_number, format_valid_phone_number, validate_other_identifier
from cashier_app.utils.products import convert_image_paths_from_relative


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
            
    for user in users:
        phone_number_formats = {
            'e164': None,
            'international': None,
            'national': None,
            'national_significant_number': None,
            'country_code': None
        }
        if user['phone_number']:
            phone_number_formats = format_valid_phone_number(user['phone_number'])

        user['phone_number'] = phone_number_formats['e164'] # už by mělo být
        user['phone_number_international'] = phone_number_formats['international']
        user['phone_number_national'] = phone_number_formats['national']
        user['phone_number_national_significant_number'] = phone_number_formats['national_significant_number']
        user['phone_number_country_code'] = phone_number_formats['country_code']
    
    return jsonify(users=users), 200


@api_bp.route('/create', methods=('POST',))
def add_user():
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
    
    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                user_id = cur.execute(
                    f'''
                    INSERT INTO users
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    RETURNING id''',
                    params).fetchone()['id']
    except IntegrityError as e:
        # uživatel se stejnými udáji už existuje: detail obsahuje unique_index_users_names_email_phone_identifier
        # email už existuje: unique_index_users_email_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

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
    except ValueError:
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
    
    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = user_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    UPDATE users
                    SET {col_updates_str}
                    WHERE id = %(id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {user_id}')
                
                # delete wallets?

    except IntegrityError as e:
        # uživatel se stejnými udáji už existuje: detail obsahuje unique_index_users_names_email_phone_identifier
        # email už existuje: unique_index_users_email_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for user id %s', user_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
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
    except ValueError:
        return jsonify(error='invalid_user_id'), 400
    
    if not user_id:
        return jsonify(error='missing_user_id'), 400

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    UPDATE users
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (user_id,))
                
                # wallets od user se smažou sami
                
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {user_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for user id %s', user_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
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
    except ValueError:
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
    # change_balance_by = request.form.get('change-balance-by', '')
    # new_balance = request.form.get('new-balance', '')

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
        return jsonify(error='missing-idempotency-key'), 400 ##### do on frontend errs

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
    
    if change_balance_by != new_balance:
        return jsonify(error=f"change_balance_by_and_new_balance_do_not_match"), 400

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                wallet = cur.execute(
                    f'''
                    INSERT INTO wallets
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    RETURNING id, owner_id''',
                    params)
                
                fingerprint_cols = {
                    'tag_id': tag_id,
                    'wallet_id': wallet['id'],
                    'user_id': wallet['owner_id'],
                    'event_id': selected_event['id'],
                    'booth_id': selected_booth['id'],
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
                'event_id': selected_event['id'],
                'booth_id': selected_booth['id'],
                'transaction_type': 'balance-change',
                'amount_czk': change_balance_by,
                'performed_by': logged_employee['id'],
                'idempotency_key': idemp_key,
                'request_fingerprint': request_fingerprint
                }
                
                cols_str = ', '.join(params.keys())
                col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

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

                if inserted:
                    return jsonify(), 200
                
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
                    return jsonify(error='idempotency_key_conflict'), 409 ##### do on frontend errs
    except RaiseException as e:
        text = str(e)

        if "insufficient balance" in text:
            return jsonify(error='wallet_balance_czk_is_not_enough'), 400 # add this to the part above if it is in transaction and to frontend errors
        else:
            return jsonify(error='unexpected_error'), 500
    except IntegrityError as e: #
        # tag_id pro event_id už existuje: detail obsahuje unique_index_event_tag_id_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


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

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    UPDATE wallets
                    SET deleted_at = now()
                    WHERE tag_id = %s
                    AND deleted_at IS NULL''',
                    (tag_id,))
                
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for tag_id {tag_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for wallet tag id %s', tag_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='wallet_not_found'), 404

    return jsonify(), 200
