"""Modul pro správu událostí (eventů) - CRUD operace, statistiky, historie transakcí a kaskádové mazání/obnovení."""

from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, g, jsonify, url_for, request, render_template
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.employee_events_booths import load_selected_event, require_event_selected
from cashier_app.auth import load_logged_in_employee, require_login, require_admin
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import convert_image_paths_from_relative
from cashier_app.utils.employees_users import is_manager, add_more_phone_number_info
from cashier_app.errors import MultipleRowsAffectedError, NoRowsAffectedError
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.cascade_capture import capture_event_cascade, convert_dict_to_serializable
from cashier_app.utils.general import get_constraint_name

bp = Blueprint('events', __name__, url_prefix='/events')


@bp.route('/manager')
def get_events_manager_page():
    """Vrátí stránku správce událostí se seznamem všech událostí."""
    return render_template('event_managers/events_manager.html')


@bp.route('/<uuid:event_id>/manager')
def get_event_manager_page(event_id):
    """Vrátí stránku správy konkrétní události podle jejího ID."""
    return render_template('event_managers/event_manager.html')


api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


@api_bp.route('')
@require_login
def get_events_to_manage():
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if g.employee['is_admin']:
                events = cur.execute(
                    '''
                    SELECT id, name, start_at, end_at, created_at
                    FROM events
                    WHERE deleted_at IS NULL
                    ORDER BY name, id''').fetchall()
            else:
                events = cur.execute(
                    '''
                    SELECT e.id, e.name, e.start_at, e.end_at, e.created_at
                    FROM events as e
                    JOIN employee_event_booth_roles AS r ON r.event_id = e.id
                    WHERE e.deleted_at IS NULL
                    AND employee_id = %s
                    AND booth_id IS NULL
                    ORDER BY e.name, e.id''',
                    (g.employee['id'],)).fetchall()

    return jsonify(events=events), 200


@api_bp.route('/<uuid:event_id>')
@require_login
def get_event(event_id):
    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event = cur.execute(
                '''
                SELECT id, name, start_at, end_at, created_at, created_by
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()

            if event is None:
                return jsonify(error='event_not_found', redirect_url=url_for('events.get_events_manager_page')), 404

            employees = cur.execute(
                '''
                SELECT em.id, em.username, em.email,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', link.booth_id, 'role', link.role, 'name', booths.name)
                        ) FILTER (WHERE link.booth_id IS NOT NULL AND booths.deleted_at IS NULL),
                        '[]'
                    ) AS booths
                FROM employees AS em
                JOIN employee_event_booth_roles AS link ON link.employee_id = em.id
                LEFT JOIN booths ON booths.id = link.booth_id
                WHERE em.deleted_at IS NULL
                AND em.is_admin IS FALSE
                AND link.event_id = %s
                GROUP BY em.id
                ORDER BY em.username, em.id''',
                (event_id,)).fetchall()

            products = cur.execute(
                '''
                SELECT p.id, p.name, p.price, img.image_path, img.image_filename,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL AND booths.deleted_at IS NULL),
                        '[]'
                    ) AS booths,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', cat_link.category_id, 'name', cat.name)
                        ) FILTER (WHERE cat_link.category_id IS NOT NULL AND cat.deleted_at IS NULL),
                        '[]'
                    ) AS categories
                FROM products as p
                LEFT JOIN product_images AS img ON img.id = p.image_id
                LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE p.event_id = %s
                AND p.deleted_at IS NULL
                GROUP BY p.id, img.id
                ORDER BY p.name, p.id''',
                (event_id,)).fetchall()


            booths = cur.execute(
                '''
                SELECT id, name, booth_type
                FROM booths
                WHERE event_id = %s
                AND deleted_at IS NULL
                ORDER BY name, id''',
                (event_id,)).fetchall()

            categories = cur.execute(
                '''
                SELECT cat.id, cat.name,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL AND booths.deleted_at IS NULL),
                        '[]'
                    ) AS booths,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', pr_link.product_id, 'name', pr.name)
                        ) FILTER (WHERE pr_link.product_id IS NOT NULL AND pr.deleted_at IS NULL),
                        '[]'
                    ) AS products
                FROM categories AS cat
                LEFT JOIN category_booth_link AS bo_link ON bo_link.category_id = cat.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                LEFT JOIN category_product_link AS pr_link ON pr_link.category_id = cat.id
                LEFT JOIN products AS pr ON pr.id = pr_link.product_id
                WHERE cat.event_id = %s
                AND cat.deleted_at IS NULL
                GROUP BY cat.id''',
                (event_id,)).fetchall()

            users = cur.execute(
                '''
                SELECT u.id, u.first_name, u.last_name, u.email, u.phone_number, u.other_identifier,
                    CASE
                    WHEN EXISTS (
                        SELECT 1 FROM wallets w
                        WHERE w.owner_id = u.id AND w.event_id = %s AND w.deleted_at IS NULL
                    ) OR EXISTS (
                        SELECT 1 FROM transactions t
                        WHERE t.user_id = u.id AND t.event_id = %s
                    ) THEN true
                    ELSE false
                    END as event_connected
                FROM users u
                WHERE u.deleted_at IS NULL
                ORDER BY u.first_name, u.last_name, u.id''',
                (event_id, event_id)).fetchall()

            wallets = cur.execute(
                '''
                SELECT w.id, w.tag_id, w.balance_czk, w.owner_id,
                    u.first_name, u.last_name
                FROM wallets w
                LEFT JOIN users u ON u.id = w.owner_id
                WHERE w.event_id = %s
                AND w.deleted_at IS NULL
                ORDER BY w.owner_id, w.tag_id, w.id''',
                (event_id,)).fetchall()

    add_more_phone_number_info(users)
    convert_image_paths_from_relative(products)

    return jsonify(event=event, employees=employees, products=products, booths=booths, categories=categories, users=users, wallets=wallets), 200


@api_bp.route('/create', methods=('POST',))
@require_admin
def add_event():
    name = request.form.get('name', '').strip()
    start_at = request.form.get('start-at', '').strip()
    end_at = request.form.get('end-at', '').strip()

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400

    params = {
        'name': name,
        'created_by': g.employee['id']
    }

    start_at_utc = None
    end_at_utc = None

    if start_at:
        try:
            start_at_dt = parser.isoparse(start_at)
            start_at_utc = start_at_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return jsonify(error='invalid_start_at'), 400
        params['start_at'] = start_at_utc

    if end_at:
        try:
            end_at_dt = parser.isoparse(end_at)
            end_at_utc = end_at_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return jsonify(error='invalid_end_at'), 400

        params['end_at'] = end_at_utc

    if start_at_utc and end_at_utc:
        if start_at_utc > end_at_utc:
            return jsonify(error='invalid_start_at_end_at_dates'), 400

    sql, query_params = build_insert_statement('events', params, returning='*')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                new_event = cur.execute(sql, query_params).fetchone()

                save_change(cur, [{
                    'table': 'events',
                    'old_values': None,
                    'new_values': convert_dict_to_serializable(dict(new_event))
                }], g.employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_events_name_active':
            return jsonify(error='event_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200


@api_bp.route('/edit', methods=('POST',))
@require_login
def edit_event():
    event_id = request.form.get('id')

    if not event_id:
        return jsonify(error='missing_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    name = request.form.get('name', '').strip()
    start_at = request.form.get('start-at', '').strip()
    end_at = request.form.get('end-at', '').strip()

    params = {}

    start_at_utc = None
    end_at_utc = None

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if start_at:
        try:
            start_at_dt = parser.isoparse(start_at)
            start_at_utc = start_at_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return jsonify(error='invalid_start_at'), 400
        params['start_at'] = start_at_utc
    else:
        params['start_at'] = None

    if end_at:
        try:
            end_at_dt = parser.isoparse(end_at)
            end_at_utc = end_at_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return jsonify(error='invalid_end_at'), 400

        params['end_at'] = end_at_utc
    else:
        params['end_at'] = None

    if start_at_utc and end_at_utc:
        if start_at_utc > end_at_utc:
            return jsonify(error='invalid_start_at_end_at_dates'), 400

    sql, query_params = build_update_statement('events', params, event_id, returning='*')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                old_event = cur.execute(
                    'SELECT * FROM events WHERE id = %s AND deleted_at IS NULL',
                    (event_id,)
                ).fetchone()

                if not old_event:
                    raise NoRowsAffectedError()

                old_values = convert_dict_to_serializable(dict(old_event))

                new_event = cur.execute(sql, query_params).fetchone()

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                new_values = convert_dict_to_serializable(dict(new_event))

                save_change(cur, [{
                    'table': 'events',
                    'old_values': old_values,
                    'new_values': new_values
                }], g.employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_events_name_active':
            return jsonify(error='event_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows updated for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='event_not_found'), 404

    return jsonify(), 200



@api_bp.route('/delete', methods=('DELETE',))
@require_login
def delete_event():
    event_id = request.form.get('id')

    if not event_id:
        return jsonify(error='missing_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    sql, query_params = build_delete_statement('events', event_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                changes = capture_event_cascade(cur, event_id)

                if not changes:
                    raise NoRowsAffectedError()

                cur.execute(sql, query_params)

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                # Cascade delete all children
                # 1. Delete link rows (hard delete)
                cur.execute(
                    '''DELETE FROM product_booth_link
                       WHERE booth_id IN (SELECT id FROM booths WHERE event_id = %s AND deleted_at IS NULL)''',
                    (event_id,))
                cur.execute(
                    '''DELETE FROM category_booth_link
                       WHERE booth_id IN (SELECT id FROM booths WHERE event_id = %s AND deleted_at IS NULL)''',
                    (event_id,))
                cur.execute(
                    '''DELETE FROM category_product_link
                       WHERE product_id IN (SELECT id FROM products WHERE event_id = %s AND deleted_at IS NULL)
                       OR category_id IN (SELECT id FROM categories WHERE event_id = %s AND deleted_at IS NULL)''',
                    (event_id, event_id))

                # 2. Delete employee roles (hard delete)
                cur.execute(
                    'DELETE FROM employee_event_booth_roles WHERE event_id = %s',
                    (event_id,))

                # 3. Soft-delete booths, products, categories
                cur.execute(
                    'UPDATE booths SET deleted_at = now() WHERE event_id = %s AND deleted_at IS NULL',
                    (event_id,))
                cur.execute(
                    'UPDATE products SET deleted_at = now() WHERE event_id = %s AND deleted_at IS NULL',
                    (event_id,))
                cur.execute(
                    'UPDATE categories SET deleted_at = now() WHERE event_id = %s AND deleted_at IS NULL',
                    (event_id,))
                cur.execute(
                    'UPDATE wallets SET deleted_at = now() WHERE event_id = %s AND deleted_at IS NULL',
                    (event_id,))

                save_change(cur, changes, g.employee['id'])
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='event_not_found'), 404

    return jsonify(redirect_url=url_for('events.get_events_manager_page')), 200


@api_bp.route('/deleted')
@require_admin
def get_deleted_events():

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            events = cur.execute(
                '''
                SELECT id, name, start_at, end_at, deleted_at
                FROM events
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC, id''',
            ).fetchall()

    return jsonify(events=events), 200


@api_bp.route('/restore', methods=('POST',))
@require_admin
def restore_event():
    try:
        event_id = UUID(request.form.get('event-id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_event_id'), 400

    force = request.form.get('force') == 'true'

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                event = cur.execute(
                    '''SELECT deleted_at, name
                    FROM events WHERE id = %s AND deleted_at IS NOT NULL''',
                    (event_id,)
                ).fetchone()

                if event is None:
                    return jsonify(error='event_not_found'), 404

                event_deleted_at = event['deleted_at']

                if force:
                    name = event['name']

                    existing = cur.execute(
                        'SELECT 1 FROM events WHERE lower(name) = lower(%s) AND deleted_at IS NULL',
                        (name,)
                    ).fetchone()
                    if existing:
                        base_name = name
                        suffix = 1
                        new_name = f"{base_name}_{suffix}"
                        while cur.execute(
                            'SELECT 1 FROM events WHERE lower(name) = lower(%s) AND deleted_at IS NULL',
                            (new_name,)
                        ).fetchone():
                            suffix += 1
                            new_name = f"{base_name}_{suffix}"
                        cur.execute('UPDATE events SET name = %s WHERE id = %s', (new_name, event_id))

                # restore the event
                cur.execute(
                    'UPDATE events SET deleted_at = NULL WHERE id = %s AND deleted_at IS NOT NULL',
                    (event_id,)
                )

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                # restore children that were deleted as a result of the event deletion
                cur.execute(
                    'UPDATE booths SET deleted_at = NULL WHERE event_id = %s AND deleted_at = %s',
                    (event_id, event_deleted_at)
                )
                cur.execute(
                    'UPDATE products SET deleted_at = NULL, image_id = NULL WHERE event_id = %s AND deleted_at = %s',
                    (event_id, event_deleted_at)
                )
                cur.execute(
                    'UPDATE categories SET deleted_at = NULL WHERE event_id = %s AND deleted_at = %s',
                    (event_id, event_deleted_at)
                )
                cur.execute(
                    'UPDATE wallets SET deleted_at = NULL WHERE event_id = %s AND deleted_at = %s',
                    (event_id, event_deleted_at)
                )
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_events_name_active':
            return jsonify(error='event_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows restored for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='event_not_found'), 404

    return jsonify(), 200


@api_bp.route('/wallets')
@require_login
@require_event_selected
def get_event_wallets():
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            wallets = cur.execute(
                '''
                SELECT tag_id, owner_id, balance_czk
                FROM wallets
                WHERE event_id = %s
                AND deleted_at IS NULL''',
                (g.event['id'],)).fetchall()

    return jsonify(wallets=wallets), 200


# Register sub-blueprints
from cashier_app.events.booths import api_booths_bp
from cashier_app.events.products import api_products_bp
from cashier_app.events.categories import api_categories_bp
from cashier_app.events.event_employees import api_employees_bp
from cashier_app.events.transaction_history import api_transaction_history_bp
from cashier_app.events.statistics import api_statistics_bp
from cashier_app.events.exports import api_exports_bp

api_bp.register_blueprint(api_booths_bp)
api_bp.register_blueprint(api_products_bp)
api_bp.register_blueprint(api_categories_bp)
api_bp.register_blueprint(api_employees_bp)
api_bp.register_blueprint(api_transaction_history_bp)
api_bp.register_blueprint(api_statistics_bp)
api_bp.register_blueprint(api_exports_bp)
