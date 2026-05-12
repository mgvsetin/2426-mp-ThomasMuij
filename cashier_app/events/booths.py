"""Modul pro správu stánků – vytváření, úprava, mazání a načítání produktů a kategorií stánku."""

from flask import Blueprint, current_app, g, jsonify, url_for, request
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth, require_event_selected, require_booth_selected
from cashier_app.auth import load_logged_in_employee, require_login
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import convert_image_paths_from_relative
from cashier_app.utils.employees_users import is_manager
from cashier_app.errors import MultipleRowsAffectedError, NoRowsAffectedError
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.cascade_capture import capture_booth_cascade, convert_dict_to_serializable
from cashier_app.utils.link_sync import sync_booth_product_links, sync_booth_category_links
from cashier_app.utils.general import get_constraint_name

api_booths_bp = Blueprint('booths', __name__, url_prefix='/booths')


@api_booths_bp.route('/create', methods=('POST',))
@require_login
def add_booth():
    """Vytvoří nový stánek v rámci akce.

    Ověří přihlášení zaměstnance a jeho oprávnění (admin nebo manažer akce).
    Validuje název a typ stánku, volitelně přiřadí produkty a kategorie.
    Pokladní stánek nesmí mít přiřazené produkty ani kategorie.
    Uloží změnu pro funkci zpět/vpřed.
    """
    event_id = request.form.get('event-id')

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    name = request.form.get('name', '').strip()
    booth_type = request.form.get('type', '').strip()

    params = {
        'created_by': g.employee['id'],
        'event_id': event_id
    }

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if not booth_type:
        return jsonify(error='missing_type'), 400

    if booth_type not in ['seller', 'cashier']:
        return jsonify(error='invalid_type'), 400
    params['booth_type'] = booth_type

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_product_id'), 400

    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_category_id'), 400

    if booth_type == 'cashier' and (product_ids or category_ids):
        return jsonify(error='cashier_cannot_have_products_or_categories'), 400

    sql, query_params = build_insert_statement('booths', params, returning='*')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                for product_id in product_ids:
                    product = cur.execute(
                        '''
                        SELECT 1
                        FROM products
                        WHERE id = %s
                        AND event_id = %s''',
                        (product_id, event_id)).fetchone()

                    if not product:
                        return jsonify(error='product_not_found'), 400

                for category_id in category_ids:
                    category = cur.execute(
                        '''
                        SELECT 1
                        FROM categories
                        WHERE id = %s
                        AND event_id = %s''',
                        (category_id, event_id)).fetchone()

                    if not category:
                        return jsonify(error='category_not_found'), 400

                new_booth = cur.execute(sql, query_params).fetchone()
                booth_id = new_booth['id']

                changes = [{
                    'table': 'booths',
                    'old_values': None,
                    'new_values': convert_dict_to_serializable(dict(new_booth))
                }]

                changes.extend(sync_booth_product_links(cur, booth_id, product_ids))
                changes.extend(sync_booth_category_links(cur, booth_id, category_ids))

                save_change(cur, changes, g.employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_booths_event_id_name_active':
            return jsonify(error='booth_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200


@api_booths_bp.route('/edit', methods=('POST',))
@require_login
def edit_booth():
    """Upraví existující stánek.

    Ověří přihlášení zaměstnance a jeho oprávnění (admin nebo manažer akce).
    Validuje nový název stánku a synchronizuje přiřazené produkty a kategorie.
    Pokladní stánek nesmí mít přiřazené produkty ani kategorie.
    Uloží staré a nové hodnoty pro funkci zpět/vpřed.
    """
    booth_id = request.form.get('id')

    if not booth_id:
        return jsonify(error='missing_id'), 400

    try:
        booth_id = UUID(booth_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            booth = cur.execute(
                '''
                SELECT event_id, booth_type
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not booth:
        return jsonify(error='booth_not_found'), 404

    event_id = booth['event_id']
    booth_type = booth['booth_type']

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    name = request.form.get('name', '').strip()

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_product_id'), 400

    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_category_id'), 400

    if booth_type == 'cashier' and (product_ids or category_ids):
        return jsonify(error='cashier_cannot_have_products_or_categories'), 400

    sql, query_params = build_update_statement('booths', params, booth_id, returning='*')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                for product_id in product_ids:
                    product = cur.execute(
                        '''
                        SELECT 1
                        FROM products
                        WHERE id = %s
                        AND event_id = %s''',
                        (product_id, event_id)).fetchone()

                    if not product:
                        return jsonify(error='product_not_found'), 400

                for category_id in category_ids:
                    category = cur.execute(
                        '''
                        SELECT 1
                        FROM categories
                        WHERE id = %s
                        AND event_id = %s''',
                        (category_id, event_id)).fetchone()

                    if not category:
                        return jsonify(error='category_not_found'), 400

                old_booth = cur.execute(
                    'SELECT * FROM booths WHERE id = %s AND deleted_at IS NULL',
                    (booth_id,)
                ).fetchone()

                if not old_booth:
                    raise NoRowsAffectedError()

                old_values = convert_dict_to_serializable(dict(old_booth))

                new_booth = cur.execute(sql, query_params).fetchone()

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                new_values = convert_dict_to_serializable(dict(new_booth))

                changes = [{
                    'table': 'booths',
                    'old_values': old_values,
                    'new_values': new_values
                }]

                changes.extend(sync_booth_product_links(cur, booth_id, product_ids))
                changes.extend(sync_booth_category_links(cur, booth_id, category_ids))

                save_change(cur, changes, g.employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_booths_event_id_name_active':
            return jsonify(error='booth_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200


@api_booths_bp.route('/delete', methods=('DELETE',))
@require_login
def delete_booth():
    """Smaže stánek (soft-delete).

    Ověří přihlášení zaměstnance a jeho oprávnění (admin nebo manažer akce).
    Zachytí kaskádové změny před smazáním, odstraní vazby na produkty,
    kategorie a role zaměstnanců u stánku.
    Uloží změny pro funkci zpět/vpřed.
    """
    booth_id = request.form.get('id')

    if not booth_id:
        return jsonify(error='missing_id'), 400

    try:
        booth_id = UUID(booth_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            booth_row = cur.execute(
                '''
                SELECT event_id
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not booth_row:
        return jsonify(error='booth_not_found'), 404

    event_id = booth_row['event_id']

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    sql, query_params = build_delete_statement('booths', booth_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                changes = capture_booth_cascade(cur, booth_id)

                if not changes:
                    raise NoRowsAffectedError()

                cur.execute(sql, query_params)

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                sync_booth_product_links(cur, booth_id, [])
                sync_booth_category_links(cur, booth_id, [])

                cur.execute(
                    'DELETE FROM employee_event_booth_roles WHERE booth_id = %s',
                    (booth_id,)
                )

                save_change(cur, changes, g.employee['id'])
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200


@api_booths_bp.route('/products-categories')
@require_login
@require_event_selected
@require_booth_selected
def get_products_and_categories():
    """Vrátí produkty a kategorie dostupné pro vybraný stánek."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            products = cur.execute(
                '''
                SELECT p.id, p.name, p.price, img.image_path,
                  COALESCE(jsonb_agg(
                      DISTINCT jsonb_build_object('name', cat.name)
                      ) FILTER (WHERE cat_link.category_id IS NOT NULL AND cat.deleted_at IS NULL),
                      '[]'
                  ) AS categories
                FROM products AS p
                LEFT JOIN product_images AS img ON img.id = p.image_id
                JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE bo_link.booth_id = %s
                AND p.deleted_at IS NULL
                GROUP BY p.id, img.id''',
                (g.booth['id'],)).fetchall()

            categories = cur.execute(
                '''
                SELECT cat.name
                FROM categories AS cat
                JOIN category_booth_link AS link ON link.category_id = cat.id
                WHERE link.booth_id = %s
                AND cat.deleted_at IS NULL''',
                (g.booth['id'],)).fetchall()

    convert_image_paths_from_relative(products)

    return jsonify(products=products, categories=categories), 200
