from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.employee_events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.employees import is_manager

bp = Blueprint('events', __name__, url_prefix='/events')


@bp.route('/manager')
def get_events_manager_page():
    # employee = load_logged_in_employee()

    # if employee is None:
    #     return redirect(url_for('auth.get_login_page'))

    # # if not employee['is_admin'] and not is_manager(employee['id'], event_id):
    # #     return jsonify(error='insufficient_priviliges'), 403

    return current_app.send_static_file('html/event_managers/events_manager.html')


@bp.route('/<uuid:event_id>/manager')
def get_event_manager_page(event_id):
    # employee = load_logged_in_employee()

    # if employee is None:
    #     return redirect(url_for('auth.get_login_page'))

    # if not employee['is_admin'] and not is_manager(employee['id'], event_id):
    #     return jsonify(error='insufficient_priviliges'), 403

    return current_app.send_static_file('html/event_managers/event_manager.html')


api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


@api_bp.route('')
def get_events_to_manage():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                events = cur.execute('''
                    SELECT id, name, start_at, end_at, created_at
                    FROM events
                    WHERE deleted_at IS NULL
                    ORDER BY created_at''').fetchall()
    else:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                events = cur.execute('''
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
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not employee['is_admin'] and not is_manager(employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event = cur.execute('''
                SELECT id, name, start_at, end_at, created_at, created_by
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()
            
            if event is None:
                return jsonify(error='event_not_found'), 404
            
            employees = cur.execute('''
                SELECT em.id, em.username, em.email,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', link.booth_id, 'role', link.role, 'name', booths.name)
                        ) FILTER (WHERE link.booth_id IS NOT NULL),
                        '[]'
                    ) AS booths
                FROM employees AS em
                JOIN employee_event_booth_roles AS link ON link.employee_id = em.id
                LEFT JOIN booths ON booths.id = link.booth_id
                WHERE em.deleted_at IS NULL
                AND link.event_id = %s
                GROUP BY em.id
                ORDER BY em.created_at''',
                (event_id,)).fetchall()
            
            # i need to show and allow uploads/changes of images on the frontend
            products = cur.execute('''
                SELECT p.id, p.name, p.price, p.image_path, p.image_filename,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL),
                        '[]'
                    ) AS booths,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', cat_link.selectable_category_id, 'name', cat.name)
                        ) FILTER (WHERE cat_link.selectable_category_id IS NOT NULL),
                        '[]'
                    ) AS categories
                FROM products as p
                LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                LEFT JOIN selectable_category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN selectable_categories AS cat ON cat.id = cat_link.selectable_category_id
                WHERE p.event_id = %s
                GROUP BY p.id
                ORDER BY p.created_at''',
                (event_id,)).fetchall()
            
            
            booths = cur.execute('''
                SELECT id, name, booth_type
                FROM booths
                WHERE event_id = %s
                AND deleted_at IS NULL
                ORDER BY created_at''',
                # '''
                # SELECT b.id, b.name, b.booth_type,
                #     COALESCE(jsonb_agg(
                #         DISTINCT jsonb_build_object('category_id', link.selectable_category_id, 'category_name', cat.name)
                #         ) FILTER (WHERE link.selectable_category_id IS NOT NULL), -- filter, aby nebyly null values, když nemá category
                #         '[]'
                #     ) AS categories
                # FROM booths AS b
                # LEFT JOIN selectable_category_booth_link AS link ON link.booth_id = b.id
                # LEFT JOIN selectable_categories AS cat ON cat.id = link.selectable_category_id
                # WHERE b.event_id = %s
                # AND b.deleted_at IS NULL
                # GROUP BY b.id,
                # ORDER BY b.created_at''',
                (event_id,)).fetchall()
            
            categories = cur.execute('''
                SELECT cat.id, cat.name,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL),
                        '[]'
                    ) AS booths
                FROM selectable_categories AS cat
                LEFT JOIN selectable_category_booth_link AS bo_link ON bo_link.selectable_category_id = cat.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                WHERE cat.event_id = %s
                GROUP BY cat.id''',
                (event_id,)).fetchall()
            
    return jsonify(event=event, employees=employees, products=products, booths=booths, categories=categories), 200


@api_bp.route('/create', methods=('POST',))
def add_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not logged_employee['is_admin']:
        return jsonify(error='insufficient_priviliges'), 403

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
        
        # if end_at_utc < datetime.now():
        #     return jsonify(error='invalid_end_at_date'), 400

        params['end_at'] = end_at_utc
    
    # if start_at_utc and end_at_utc:
    #     if start_at_utc > end_at_utc:
    #         return jsonify(error='invalid_start_at_end_at_dates'), 400

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f'''
                    INSERT INTO events
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    params)
    except IntegrityError as e:
        # jméno už existuje: detail = unique_index_events_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_bp.route('/edit', methods=('POST',))
def edit_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not event_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

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
        
        # if end_at_utc < datetime.now():
        #     return jsonify(error='invalid_end_at_date'), 400

        params['end_at'] = end_at_utc
    else:
        params['end_at'] = None
    
    if start_at_utc and end_at_utc:
        if start_at_utc > end_at_utc:
            return jsonify(error='invalid_start_at_end_at_dates'), 400

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = event_id
    # validate start_at end_at from db?

    # add editing event info from other tables
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f'''
                    UPDATE events
                    SET {col_updates_str}
                    WHERE id = %(id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {event_id}')
    except IntegrityError as e:
        # jestli někdy půjde nastavit start_at nebo end_at, když už je jedna hodnotav db,
        # tak se musí ověření start_at <= end_at vzít z db (detail=events_start_at_before_end_at_check)
        # jméno už existuje: detail = unique_index_events_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500

    if rows_affected == 0:
        return jsonify(error='event_not_found'), 404

    return jsonify(), 200



@api_bp.route('/delete', methods=('DELETE',))
def delete_event():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not event_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE events
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (event_id,))

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {event_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for event id %s', event_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='event_not_found'), 404

    return jsonify(redirect_url=url_for('events.get_events_manager_page')), 200
