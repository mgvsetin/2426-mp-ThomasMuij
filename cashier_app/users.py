"""Modul pro správu uživatelů.

Obsahuje API endpointy pro vytváření, úpravu, mazání a obnovení uživatelů.
"""

from flask import Blueprint, current_app, g, jsonify, url_for, request
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee, require_login
from cashier_app.db import get_pool
from cashier_app.utils.general import get_constraint_name
from cashier_app.utils.employees_users import validate_email, validate_first_or_last_name, validate_phone_number, format_valid_phone_number, add_more_phone_number_info, validate_other_identifier
from cashier_app.errors import NoRowsAffectedError, MultipleRowsAffectedError
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement


api_bp = Blueprint('users_api', __name__, url_prefix='/api/users')


@api_bp.route('')
@require_login
def get_users():
    """Získá seznam všech aktivních (nesmazaných) uživatelů."""
    if not g.employee['is_admin']:
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
                SELECT id, first_name, last_name, email, phone_number, other_identifier
                FROM users
                WHERE deleted_at IS NULL
                ORDER BY first_name, last_name, id''',
                ).fetchall()
            
    add_more_phone_number_info(users)
    
    return jsonify(users=users), 200


def _validate_user_get_params_or_response(
        first_name,
        last_name,
        email,
        phone_number,
        country_code,
        other_identifier):
    """Zvaliduje údaje uživatele a vrátí slovník parametrů nebo chybovou odpověď."""
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

    return params


@api_bp.route('/create', methods=('POST',))
@require_login
def add_user():
    """Vytvoří nového uživatele s validovanými údaji."""
    if not g.employee['is_admin']:
        selected_event = load_selected_event()
        selected_booth = load_selected_booth()
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (g.employee['id'],)
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
    
    output = _validate_user_get_params_or_response(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        country_code=country_code,
        other_identifier=other_identifier
    )

    if isinstance(output, tuple):
        return output
    params = output
    
    sql, query_params = build_insert_statement('users', params, returning=['id'])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                user_id = cur.execute(sql, query_params).fetchone()['id']
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_users_names_email_phone_identifier':
            return jsonify(error='user_identifier_taken'), 409
        if constraint == 'unique_index_users_email_active':
            return jsonify(error='user_email_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(user_id=user_id), 200


@api_bp.route('/edit', methods=('POST',))
@require_login
def edit_user():
    """Upraví údaje existujícího uživatele."""
    if not g.employee['is_admin']:
        selected_event = load_selected_event()
        selected_booth = load_selected_booth()
        if selected_event is None:
            return jsonify(error='no_selected_event'), 400

        if selected_booth is None:
            return jsonify(error='no_selected_booth'), 400
        
        if selected_booth['booth_type'] != 'cashier':
            return jsonify(error='invalid_booth_type'), 400
        
    user_id = request.form.get('user-id')
    if not user_id:
        return jsonify(error='missing_user_id'), 400

    try:
        user_id = UUID(user_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400
    
    
    
    first_name = request.form.get('first-name', '').strip().capitalize()
    last_name = request.form.get('last-name', '').strip().capitalize()
    email = request.form.get('email', '').strip().lower()
    country_code = request.form.get('phone-number-country-code', '').strip()
    phone_number = request.form.get('phone-number', '').strip()
    other_identifier = request.form.get('other-identifier', '').strip()
    
    output = _validate_user_get_params_or_response(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        country_code=country_code,
        other_identifier=other_identifier
    )

    if isinstance(output, tuple):
        return output
    params = output
    
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

    except IntegrityError as e:
        constraint = get_constraint_name(e)

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
@require_login
def delete_user():
    """Soft-delete uživatele (nastaví deleted_at)."""
    if not g.employee['is_admin']:
        selected_event = load_selected_event()
        selected_booth = load_selected_booth()
        if selected_event is None:
            return jsonify(error='no_selected_event'), 400

        if selected_booth is None:
            return jsonify(error='no_selected_booth'), 400
        
        if selected_booth['booth_type'] != 'cashier':
            return jsonify(error='invalid_booth_type'), 400
        
    user_id = request.form.get('user-id')

    if not user_id:
        return jsonify(error='missing_user_id'), 400
        
    try:
        user_id = UUID(user_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_user_id'), 400

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
@require_login
def get_deleted_users():
    """Získá seznam všech smazaných uživatelů."""
    if not g.employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (g.employee['id'],)
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
                ORDER BY deleted_at DESC, id''',
            ).fetchall()

    add_more_phone_number_info(users)

    return jsonify(users=users), 200


@api_bp.route('/restore', methods=('POST',))
@require_login
def restore_user():
    """Obnoví smazaného uživatele a jeho peněženky, případně vyřeší konflikty unikátnosti."""
    if not g.employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                is_any_manager = cur.execute(
                    '''
                    SELECT 1 FROM employee_event_booth_roles
                    WHERE employee_id = %s AND booth_id IS NULL
                    LIMIT 1
                    ''',
                    (g.employee['id'],)
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
        constraint = get_constraint_name(e)

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
