"""Modul pro správu událostí (eventů) - CRUD operace, statistiky, historie transakcí a kaskádové mazání/obnovení."""

from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, request, render_template
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee
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


@bp.route('/<uuid:event_id>/users/<uuid:user_id>/transaction-history')
def get_user_transaction_history_page(event_id, user_id):
    """Vrátí stránku s historií transakcí konkrétního uživatele pro danou událost."""
    return render_template('index/user_transaction_history.html')


@bp.route('/<uuid:event_id>/transaction-history')
def get_event_transaction_history_page(event_id):
    """Vrátí stránku s historií všech transakcí pro danou událost."""
    return render_template('event_managers/event_transaction_history.html')


api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


@api_bp.route('')
def get_events_to_manage():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if employee['is_admin']:
                events = cur.execute(
                    '''
                    SELECT id, name, start_at, end_at, created_at
                    FROM events
                    WHERE deleted_at IS NULL
                    ORDER BY created_at''').fetchall()
            else:
                events = cur.execute(
                    '''
                    SELECT e.id, e.name, e.start_at, e.end_at, e.created_at
                    FROM events as e
                    JOIN employee_event_booth_roles AS r ON r.event_id = e.id
                    WHERE e.deleted_at IS NULL
                    AND employee_id = %s
                    AND booth_id IS NULL
                    ORDER BY e.created_at''',
                    (employee['id'],)).fetchall()

    return jsonify(events=events), 200


@api_bp.route('/<uuid:event_id>')
def get_event(event_id):
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
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
                ORDER BY em.created_at''',
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
                ORDER BY p.created_at''',
                (event_id,)).fetchall()


            booths = cur.execute(
                '''
                SELECT id, name, booth_type
                FROM booths
                WHERE event_id = %s
                AND deleted_at IS NULL
                ORDER BY created_at''',
                (event_id,)).fetchall()

            categories = cur.execute(
                '''
                SELECT cat.id, cat.name,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL AND booths.deleted_at IS NULL),
                        '[]'
                    ) AS booths
                FROM categories AS cat
                LEFT JOIN category_booth_link AS bo_link ON bo_link.category_id = cat.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
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
                ORDER BY u.created_at''',
                (event_id, event_id)).fetchall()

            wallets = cur.execute(
                '''
                SELECT w.id, w.tag_id, w.balance_czk, w.owner_id,
                    u.first_name, u.last_name
                FROM wallets w
                LEFT JOIN users u ON u.id = w.owner_id
                WHERE w.event_id = %s
                AND w.deleted_at IS NULL
                ORDER BY w.created_at''',
                (event_id,)).fetchall()

    add_more_phone_number_info(users)
    convert_image_paths_from_relative(products)

    return jsonify(event=event, employees=employees, products=products, booths=booths, categories=categories, users=users, wallets=wallets), 200


@api_bp.route('/create', methods=('POST',))
def add_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        return jsonify(error='insufficient_privileges'), 403

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
        'created_by': logged_employee['id']
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
                }], logged_employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_events_name_active':
            return jsonify(error='event_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200


@api_bp.route('/edit', methods=('POST',))
def edit_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event_id = request.form.get('id')

    if not event_id:
        return jsonify(error='missing_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
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
                }], logged_employee['id'])
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
def delete_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event_id = request.form.get('id')

    if not event_id:
        return jsonify(error='missing_id'), 400

    try:
        event_id = UUID(event_id)
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
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

                save_change(cur, changes, logged_employee['id'])
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='event_not_found'), 404

    return jsonify(redirect_url=url_for('events.get_events_manager_page')), 200


@api_bp.route('/deleted')
def get_deleted_events():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
            return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            events = cur.execute(
                '''
                SELECT id, name, start_at, end_at, deleted_at
                FROM events
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC''',
            ).fetchall()

    return jsonify(events=events), 200


@api_bp.route('/restore', methods=('POST',))
def restore_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
            return jsonify(error='insufficient_privileges'), 403

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
def get_event_wallets():
    employee = load_logged_in_employee()
    event = load_selected_event()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if event is None:
        return jsonify(error='no_selected_event'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            wallets = cur.execute(
                '''
                SELECT tag_id, owner_id, balance_czk
                FROM wallets
                WHERE event_id = %s
                AND deleted_at IS NULL''',
                (event['id'],)).fetchall()

    return jsonify(wallets=wallets), 200


@api_bp.route('/<uuid:event_id>/users/<uuid:user_id>/transaction-history')
def get_user_transaction_history_for_event(event_id, user_id):
    logged_employee = load_logged_in_employee()
    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(str(event_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not user_id:
        return jsonify(error='missing_user_id'), 400

    try:
        user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_user_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        selected_event = load_selected_event()
        if not selected_event or selected_event['id'] != event_id:
            return jsonify(error='insufficient_privileges'), 403

        selected_booth = load_selected_booth()

        if not selected_booth or selected_booth['booth_type'] != 'cashier':
            return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            user_transaction_history = cur.execute(
                '''
                SELECT t.tag_id, t.transaction_type, t.amount_czk, t.balance_before, t.balance_after, t.occurred_at, t.products_info, e.username AS performed_by_username, b.name AS booth_name
                FROM transactions t
                JOIN users u ON u.id = t.user_id
                JOIN employees e ON e.id = t.performed_by
                JOIN booths b ON b.id = t.booth_id
                WHERE t.user_id = %s
                AND t.event_id = %s
                ORDER BY t.occurred_at
                ''',
                (user_id, event_id)).fetchall()

    return jsonify(user_transaction_history=user_transaction_history), 200


@api_bp.route('/<uuid:event_id>/transaction-history')
def get_event_transaction_history(event_id):
    logged_employee = load_logged_in_employee()
    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(str(event_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_transaction_history = cur.execute(
                '''
                SELECT t.tag_id, t.transaction_type, t.amount_czk, t.balance_before, t.balance_after, t.occurred_at, t.products_info,
                       e.username AS performed_by_username,
                       u.first_name AS user_first_name, u.last_name AS user_last_name,
                       b.name AS booth_name
                FROM transactions t
                JOIN employees e ON e.id = t.performed_by
                JOIN booths b ON b.id = t.booth_id
                LEFT JOIN users u ON u.id = t.user_id
                WHERE t.event_id = %s
                ORDER BY t.occurred_at
                ''',
                (event_id,)).fetchall()

    return jsonify(event_transaction_history=event_transaction_history), 200


@api_bp.route('/<uuid:event_id>/statistics')
def get_event_statistics(event_id):
    logged_employee = load_logged_in_employee()
    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(str(event_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event = cur.execute(
                '''
                SELECT id, name, start_at, end_at, created_at
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL
                ''',
                (event_id,)
            ).fetchone()

            if not event:
                return jsonify(error='event_not_found'), 404

            overall_stats = cur.execute(
                '''
                SELECT
                    COUNT(*) as total_transactions,
                    COUNT(DISTINCT wallet_id) as unique_wallets,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(CASE WHEN transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as total_revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as total_deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as total_withdrawals_czk
                FROM transactions t
                WHERE event_id = %s
                AND transaction_type != 'refund'
                AND NOT EXISTS (
                    SELECT 1 FROM transactions r
                    WHERE r.refunded_transaction_id = t.id
                )
                ''',
                (event_id,)
            ).fetchone()

            booth_stats = cur.execute(
                '''
                SELECT
                    b.id as booth_id,
                    b.name as booth_name,
                    b.booth_type,
                    COUNT(t.id) as transaction_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN -t.amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk > 0 THEN t.amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk < 0 THEN -t.amount_czk ELSE 0 END) as withdrawals_czk
                FROM booths b
                LEFT JOIN transactions t ON t.booth_id = b.id
                    AND t.transaction_type != 'refund'
                    AND NOT EXISTS (
                        SELECT 1 FROM transactions r
                        WHERE r.refunded_transaction_id = t.id
                    )
                WHERE b.event_id = %s AND b.deleted_at IS NULL
                GROUP BY b.id, b.name, b.booth_type
                ORDER BY revenue_czk DESC NULLS LAST
                ''',
                (event_id,)
            ).fetchall()

            product_stats = cur.execute(
                '''
                WITH product_items AS (
                    SELECT
                        t.id as transaction_id,
                        t.booth_id,
                        t.occurred_at,
                        jsonb_array_elements(t.products_info) as product_item
                    FROM transactions t
                    WHERE t.event_id = %s
                    AND t.transaction_type = 'payment'
                    AND t.products_info IS NOT NULL
                    AND jsonb_array_length(t.products_info) > 0
                    AND NOT EXISTS (
                        SELECT 1 FROM transactions r
                        WHERE r.refunded_transaction_id = t.id
                    )
                )
                SELECT
                    product_item->>'name' as product_name,
                    SUM((product_item->>'quantity')::int) as total_quantity,
                    SUM((product_item->>'price')::int * (product_item->>'quantity')::int) as total_revenue_czk,
                    AVG((product_item->>'price')::int) as avg_price_czk,
                    COUNT(DISTINCT transaction_id) as transaction_count,
                    COUNT(DISTINCT booth_id) as booth_count
                FROM product_items
                GROUP BY product_item->>'name'
                ORDER BY total_revenue_czk DESC
                ''',
                (event_id,)
            ).fetchall()

            hourly_stats = cur.execute(
                '''
                SELECT
                    DATE_TRUNC('hour', occurred_at) as hour,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk
                FROM transactions t
                WHERE event_id = %s
                AND transaction_type != 'refund'
                AND NOT EXISTS (
                    SELECT 1 FROM transactions r
                    WHERE r.refunded_transaction_id = t.id
                )
                GROUP BY DATE_TRUNC('hour', occurred_at)
                ORDER BY hour ASC
                ''',
                (event_id,)
            ).fetchall()

            daily_stats = cur.execute(
                '''
                SELECT
                    DATE_TRUNC('day', occurred_at) as day,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as withdrawals_czk
                FROM transactions t
                WHERE event_id = %s
                AND transaction_type != 'refund'
                AND NOT EXISTS (
                    SELECT 1 FROM transactions r
                    WHERE r.refunded_transaction_id = t.id
                )
                GROUP BY DATE_TRUNC('day', occurred_at)
                ORDER BY day ASC
                ''',
                (event_id,)
            ).fetchall()

            top_products = cur.execute(
                '''
                WITH product_items AS (
                    SELECT
                        jsonb_array_elements(t.products_info) as product_item
                    FROM transactions t
                    WHERE t.event_id = %s
                    AND t.transaction_type = 'payment'
                    AND t.products_info IS NOT NULL
                    AND jsonb_array_length(t.products_info) > 0
                    AND NOT EXISTS (
                        SELECT 1 FROM transactions r
                        WHERE r.refunded_transaction_id = t.id
                    )
                )
                SELECT
                    product_item->>'name' as product_name,
                    SUM((product_item->>'quantity')::int) as total_quantity,
                    SUM((product_item->>'price')::int * (product_item->>'quantity')::int) as total_revenue_czk
                FROM product_items
                GROUP BY product_item->>'name'
                ORDER BY total_revenue_czk DESC
                LIMIT 10
                ''',
                (event_id,)
            ).fetchall()

            wallet_stats = cur.execute(
                '''
                SELECT
                    COUNT(*) as total_wallets,
                    SUM(balance_czk) as total_balance_czk,
                    AVG(balance_czk) as avg_balance_czk,
                    MAX(balance_czk) as max_balance_czk,
                    MIN(balance_czk) as min_balance_czk
                FROM wallets
                WHERE event_id = %s AND deleted_at IS NULL
                ''',
                (event_id,)
            ).fetchone()

            booth_product_stats = cur.execute(
                '''
                WITH product_items AS (
                    SELECT
                        t.booth_id,
                        b.name as booth_name,
                        jsonb_array_elements(t.products_info) as product_item
                    FROM transactions t
                    JOIN booths b ON b.id = t.booth_id
                    WHERE t.event_id = %s
                    AND t.transaction_type = 'payment'
                    AND t.products_info IS NOT NULL
                    AND jsonb_array_length(t.products_info) > 0
                    AND NOT EXISTS (
                        SELECT 1 FROM transactions r
                        WHERE r.refunded_transaction_id = t.id
                    )
                )
                SELECT
                    booth_id,
                    booth_name,
                    product_item->>'name' as product_name,
                    SUM((product_item->>'quantity')::int) as total_quantity,
                    SUM((product_item->>'price')::int * (product_item->>'quantity')::int) as total_revenue_czk,
                    AVG((product_item->>'price')::int) as avg_price_czk,
                    COUNT(*) as transaction_count
                FROM product_items
                GROUP BY booth_id, booth_name, product_item->>'name'
                ORDER BY booth_name, total_revenue_czk DESC
                ''',
                (event_id,)
            ).fetchall()

    return jsonify(
        event={
            'id': event['id'],
            'name': event['name'],
            'start_at': event['start_at'].isoformat() if event['start_at'] else None,
            'end_at': event['end_at'].isoformat() if event['end_at'] else None,
            'created_at': event['created_at'].isoformat() if event['created_at'] else None
        },
        overall_statistics={
            'total_transactions': overall_stats['total_transactions'] or 0,
            'unique_wallets': overall_stats['unique_wallets'] or 0,
            'unique_users': overall_stats['unique_users'] or 0,
            'payment_count': overall_stats['payment_count'] or 0,
            'balance_change_count': overall_stats['balance_change_count'] or 0,
            'total_revenue_czk': overall_stats['total_revenue_czk'] or 0,
            'total_deposits_czk': overall_stats['total_deposits_czk'] or 0,
            'total_withdrawals_czk': overall_stats['total_withdrawals_czk'] or 0
        },
        booth_statistics=[{
            'booth_id': b['booth_id'],
            'booth_name': b['booth_name'],
            'booth_type': b['booth_type'],
            'transaction_count': b['transaction_count'] or 0,
            'payment_count': b['payment_count'] or 0,
            'balance_change_count': b['balance_change_count'] or 0,
            'revenue_czk': b['revenue_czk'] or 0,
            'deposits_czk': b['deposits_czk'] or 0,
            'withdrawals_czk': b['withdrawals_czk'] or 0
        } for b in booth_stats],
        product_statistics=[{
            'product_name': p['product_name'],
            'total_quantity': p['total_quantity'] or 0,
            'total_revenue_czk': p['total_revenue_czk'] or 0,
            'avg_price_czk': float(p['avg_price_czk']) if p['avg_price_czk'] else 0,
            'transaction_count': p['transaction_count'] or 0,
            'booth_count': p['booth_count'] or 0
        } for p in product_stats],
        top_products=[{
            'product_name': p['product_name'],
            'total_quantity': p['total_quantity'] or 0,
            'total_revenue_czk': p['total_revenue_czk'] or 0
        } for p in top_products],
        hourly_statistics=[{
            'hour': h['hour'].isoformat() if h['hour'] else None,
            'transaction_count': h['transaction_count'] or 0,
            'revenue_czk': h['revenue_czk'] or 0,
            'deposits_czk': h['deposits_czk'] or 0
        } for h in hourly_stats],
        daily_statistics=[{
            'day': d['day'].isoformat() if d['day'] else None,
            'transaction_count': d['transaction_count'] or 0,
            'revenue_czk': d['revenue_czk'] or 0,
            'deposits_czk': d['deposits_czk'] or 0,
            'withdrawals_czk': d['withdrawals_czk'] or 0
        } for d in daily_stats],
        wallet_statistics={
            'total_wallets': wallet_stats['total_wallets'] or 0,
            'total_balance_czk': wallet_stats['total_balance_czk'] or 0,
            'avg_balance_czk': float(wallet_stats['avg_balance_czk']) if wallet_stats['avg_balance_czk'] else 0,
            'max_balance_czk': wallet_stats['max_balance_czk'] or 0,
            'min_balance_czk': wallet_stats['min_balance_czk'] or 0
        },
        booth_product_statistics=[{
            'booth_id': bp['booth_id'],
            'booth_name': bp['booth_name'],
            'product_name': bp['product_name'],
            'total_quantity': bp['total_quantity'] or 0,
            'total_revenue_czk': bp['total_revenue_czk'] or 0,
            'avg_price_czk': float(bp['avg_price_czk']) if bp['avg_price_czk'] else 0,
            'transaction_count': bp['transaction_count'] or 0
        } for bp in booth_product_stats]
    ), 200


# Register sub-blueprints
from cashier_app.events.booths import api_booths_bp
from cashier_app.events.products import api_products_bp
from cashier_app.events.categories import api_categories_bp
from cashier_app.events.event_employees import api_employees_bp

api_bp.register_blueprint(api_booths_bp)
api_bp.register_blueprint(api_products_bp)
api_bp.register_blueprint(api_categories_bp)
api_bp.register_blueprint(api_employees_bp)
