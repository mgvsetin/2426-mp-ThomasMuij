"""Modul pro správu kategorií v rámci událostí.

Poskytuje API endpointy pro vytváření, úpravu a mazání kategorií,
včetně synchronizace vazeb na stánky a produkty.
"""

from flask import Blueprint, current_app, jsonify, url_for, request
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager
from cashier_app.utils.products import validate_product_or_category_name
from cashier_app.errors import MultipleRowsAffectedError, NoRowsAffectedError
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.cascade_capture import capture_category_cascade, convert_dict_to_serializable
from cashier_app.utils.link_sync import sync_category_booth_links, sync_category_product_links
from cashier_app.utils.general import get_constraint_name

api_categories_bp = Blueprint('categories', __name__, url_prefix='/categories')


@api_categories_bp.route('/create', methods=('POST',))
def add_category():
    """Vytvoří novou kategorii pro danou událost.

    Ověří přihlášení a oprávnění zaměstnance, zvaliduje vstupní data (název,
    stánky, produkty) a vloží novou kategorii do databáze. Synchronizuje
    vazby kategorie na stánky a produkty a uloží změnu pro funkci zpět/znovu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    event_id = request.form.get('event-id')

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    name = request.form.get('name', '').strip()
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_product_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    params = {
        'event_id': event_id
    }

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                event = cur.execute(
                    '''
                    SELECT 1
                    FROM events
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (event_id,)).fetchone()

                if not event:
                    return jsonify(error='event_not_found'), 400

                for booth_id in booth_ids:
                    booth = cur.execute(
                        '''
                        SELECT booth_type
                        FROM booths
                        WHERE id = %s
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (booth_id, event_id)).fetchone()

                    if not booth:
                        return jsonify(error='booth_not_found'), 400

                    if booth['booth_type'] != 'seller':
                        return jsonify(error='booth_is_not_seller'), 400

                for product_id in product_ids:
                    product = cur.execute(
                        '''
                        SELECT 1
                        FROM products
                        WHERE id = %s
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (product_id, event_id)).fetchone()

                    if not product:
                        return jsonify(error='product_not_found'), 400

                sql, query_params = build_insert_statement('categories', params, returning='*')
                new_category = cur.execute(sql, query_params).fetchone()
                category_id = new_category['id']

                changes = [{
                    'table': 'categories',
                    'old_values': None,
                    'new_values': convert_dict_to_serializable(dict(new_category))
                }]

                changes.extend(sync_category_booth_links(cur, category_id, booth_ids))
                changes.extend(sync_category_product_links(cur, category_id, product_ids))

                save_change(cur, changes, logged_employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_categories_event_id_name_active':
            return jsonify(error='category_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200


@api_categories_bp.route('/edit', methods=('POST',))
def edit_category():
    """Upraví existující kategorii.

    Ověří přihlášení a oprávnění zaměstnance, zvaliduje vstupní data (název,
    stánky, produkty) a aktualizuje kategorii v databázi. Synchronizuje vazby
    kategorie na stánky a produkty a uloží změnu pro funkci zpět/znovu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    category_id = request.form.get('id')

    if not category_id:
        return jsonify(error='missing_id'), 400

    try:
        category_id = UUID(category_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            category = cur.execute(
                '''
                SELECT event_id
                FROM categories
                WHERE id = %s
                AND deleted_at IS NULL''',
                (category_id,)).fetchone()

    if not category:
        return jsonify(error='category_not_found'), 404

    event_id = category['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    name = request.form.get('name', '').strip()
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_product_id'), 400

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                event = cur.execute(
                    '''
                    SELECT 1
                    FROM events
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (event_id,)).fetchone()

                if not event:
                    return jsonify(error='event_not_found'), 400

                for booth_id in booth_ids:
                    booth = cur.execute(
                        '''
                        SELECT booth_type
                        FROM booths
                        WHERE id = %s
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (booth_id, event_id)).fetchone()

                    if not booth:
                        return jsonify(error='booth_not_found'), 400

                    if booth['booth_type'] != 'seller':
                        return jsonify(error='booth_is_not_seller'), 400

                for product_id in product_ids:
                    product = cur.execute(
                        '''
                        SELECT 1
                        FROM products
                        WHERE id = %s
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (product_id, event_id)).fetchone()

                    if not product:
                        return jsonify(error='product_not_found'), 400

                old_category = cur.execute(
                    'SELECT * FROM categories WHERE id = %s AND deleted_at IS NULL',
                    (category_id,)
                ).fetchone()
                if not old_category:
                    raise NoRowsAffectedError()
                old_values = convert_dict_to_serializable(dict(old_category))

                sql, query_params = build_update_statement('categories', params, category_id, returning='*')
                new_category = cur.execute(sql, query_params).fetchone()

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                new_values = convert_dict_to_serializable(dict(new_category))

                changes = [{
                    'table': 'categories',
                    'old_values': old_values,
                    'new_values': new_values
                }]

                changes.extend(sync_category_booth_links(cur, category_id, booth_ids))
                changes.extend(sync_category_product_links(cur, category_id, product_ids))

                save_change(cur, changes, logged_employee['id'])

    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_categories_event_id_name_active':
            return jsonify(error='category_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for category id %s', category_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='category_not_found'), 404

    return jsonify(), 200


@api_categories_bp.route('/delete', methods=('DELETE',))
def delete_category():
    """Smaže existující kategorii (soft delete).

    Ověří přihlášení a oprávnění zaměstnance, zachytí kaskádové vazby
    kategorie, provede soft delete a odstraní vazby na stánky a produkty.
    Uloží změnu pro funkci zpět/znovu.

    Returns:
        tuple: JSON odpověď a HTTP stavový kód.
    """
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    category_id = request.form.get('id')

    if not category_id:
        return jsonify(error='missing_id'), 400

    try:
        category_id = UUID(category_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            category = cur.execute(
                '''
                SELECT event_id
                FROM categories
                WHERE id = %s
                AND deleted_at IS NULL''',
                (category_id,)).fetchone()

    if not category:
        return jsonify(error='category_not_found'), 404

    event_id = category['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    sql, query_params = build_delete_statement('categories', category_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                changes = capture_category_cascade(cur, category_id)

                if not changes:
                    raise NoRowsAffectedError()

                cur.execute(sql, query_params)

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                sync_category_booth_links(cur, category_id, [])
                sync_category_product_links(cur, category_id, [])

                save_change(cur, changes, logged_employee['id'])
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for category id %s', category_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='category_not_found'), 404

    return jsonify(), 200
