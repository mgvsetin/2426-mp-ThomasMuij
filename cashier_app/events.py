import os
from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from psycopg.errors import ForeignKeyViolation
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from cashier_app.employee_events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price, image_extension_is_allowed, verify_image_file_get_info, save_unique_stream, convert_image_paths_from_relative
from cashier_app.utils.employees import is_manager
from cashier_app.utils.products import convert_image_paths_from_relative

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
                events = cur.execute(
                    '''
                    SELECT id, name, start_at, end_at, created_at
                    FROM events
                    WHERE deleted_at IS NULL
                    ORDER BY created_at''').fetchall()
    else:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
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
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not employee['is_admin'] and not is_manager(employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

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
                return jsonify(error='event_not_found'), 404
            
            employees = cur.execute(
                '''
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
            products = cur.execute(
                '''
                SELECT p.id, p.name, p.price, p.image_path, p.image_filename,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL),
                        '[]'
                    ) AS booths,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', cat_link.category_id, 'name', cat.name)
                        ) FILTER (WHERE cat_link.category_id IS NOT NULL),
                        '[]'
                    ) AS categories
                FROM products as p
                LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE p.event_id = %s
                GROUP BY p.id
                ORDER BY p.created_at''',
                (event_id,)).fetchall()
            
            
            booths = cur.execute(
                '''
                SELECT id, name, booth_type
                FROM booths
                WHERE event_id = %s
                AND deleted_at IS NULL
                ORDER BY created_at''',
                # '''
                # SELECT b.id, b.name, b.booth_type,
                #     COALESCE(jsonb_agg(
                #         DISTINCT jsonb_build_object('category_id', link.category_id, 'category_name', cat.name)
                #         ) FILTER (WHERE link.category_id IS NOT NULL), -- filter, aby nebyly null values, když nemá category
                #         '[]'
                #     ) AS categories
                # FROM booths AS b
                # LEFT JOIN category_booth_link AS link ON link.booth_id = b.id
                # LEFT JOIN categories AS cat ON cat.id = link.category_id
                # WHERE b.event_id = %s
                # AND b.deleted_at IS NULL
                # GROUP BY b.id,
                # ORDER BY b.created_at''',
                (event_id,)).fetchall()
            
            categories = cur.execute(
                '''
                SELECT cat.id, cat.name,
                    COALESCE(jsonb_agg(
                        DISTINCT jsonb_build_object('id', bo_link.booth_id, 'name', booths.name)
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL),
                        '[]'
                    ) AS booths
                FROM categories AS cat
                LEFT JOIN category_booth_link AS bo_link ON bo_link.category_id = cat.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                WHERE cat.event_id = %s
                GROUP BY cat.id''',
                (event_id,)).fetchall()
            
    convert_image_paths_from_relative(products)
            
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
                cur.execute(
                    f'''
                    INSERT INTO events
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    params)
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_events_name_active
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
                cur.execute(
                    f'''
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
        # jméno už existuje: detail obsahuje unique_index_events_name_active
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
                cur.execute(
                    '''
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


api_booths_bp = Blueprint('booths', __name__, url_prefix='/booths')
api_bp.register_blueprint(api_booths_bp)


@api_booths_bp.route('/create', methods=('POST',))
def add_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    name = request.form.get('name', '').strip()
    booth_type = request.form.get('type', '').strip()

    params = {
        'created_by': logged_employee['id'],
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

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO booths
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    params)
    except IntegrityError as e: #
        # jméno už existuje: detail obsahuje unique_index_booths_event_id_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_booths_bp.route('/edit', methods=('POST',))
def edit_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    try:
        booth_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not booth_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_id = cur.execute(
                f'''
                SELECT event_id
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not event_id:
        return jsonify(error='booth_not_found'), 404
    
    event_id = event_id['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    name = request.form.get('name', '').strip()

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_event_or_booth_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = booth_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    UPDATE booths
                    SET {col_updates_str}
                    WHERE id = %(id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {booth_id}')
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_booths_event_id_name_active
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200


@api_booths_bp.route('/delete', methods=('DELETE',))
def delete_booth():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401
    
    try:
        booth_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not booth_id:
        return jsonify(error='missing_id'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_id = cur.execute(
                f'''
                SELECT event_id
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not event_id:
        return jsonify(error='booth_not_found'), 404
    
    event_id = event_id['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    UPDATE booths
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (booth_id,))

                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {booth_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for booth id %s', booth_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='booth_not_found'), 404

    return jsonify(), 200


api_employees_bp = Blueprint('employees', __name__, url_prefix='/employees')
api_bp.register_blueprint(api_employees_bp)


@api_employees_bp.route('/assign-manager', methods=('POST',))
def assign_manager():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id, is_admin
                FROM employees
                WHERE (username = %s OR email = %s)
                AND deleted_at IS NULL''',
                (username_or_email, username_or_email)).fetchone()
            
            event = cur.execute(
                '''
                SELECT 1
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()
    
    # integrity error nestačí, přotože deleted_at musí být NULL
    if not event:
        return jsonify(error='event_not_found'), 400
    
    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    if not employee:
        return jsonify(error='employee_not_found'), 400
    
    if employee['is_admin']:
        return jsonify(error='can_not_assign_admin'), 400
            
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'''
                DELETE FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s''',
                (employee['id'], event_id))
            
            cur.execute(
                f'''
                INSERT INTO employee_event_booth_roles
                (employee_id, event_id, booth_id)
                VALUES (%s, %s, NULL) -- role se doplní sama v db''',
                (employee['id'], event_id))

    return jsonify(), 200


@api_employees_bp.route('/assign-employee', methods=('POST',))
def assign_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400
    
    username_or_email = request.form.get('username-or-email', '').strip()

    if not username_or_email:
        return jsonify(error='missing_username_or_email'), 400
    
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except ValueError:
        return jsonify(error='invalid_booth_id'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:            
            event = cur.execute(
                '''
                SELECT 1
                FROM events
                WHERE id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()
            
            # integrity error nestačí, přotože deleted_at musí být NULL
            if not event:
                return jsonify(error='event_not_found'), 400
            
            for booth_id in booth_ids:
                booth = cur.execute(
                    '''
                    SELECT 1
                    FROM booths
                    WHERE id = %s
                    AND event_id = %s
                    AND deleted_at IS NULL''',
                    (booth_id, event_id)).fetchone()
                
                if not booth:
                    return jsonify(error='booth_not_found'), 400
                
            employee = cur.execute(
                '''
                SELECT id, is_admin
                FROM employees
                WHERE (username = %s OR email = %s)
                AND deleted_at IS NULL''',
                (username_or_email, username_or_email)).fetchone()
            
            if not employee:
                return jsonify(error='employee_not_found'), 400
            
            if employee['is_admin']:
                return jsonify(error='can_not_assign_admin'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403
            
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            role_row = cur.execute(
                f'''
                SELECT role
                FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s
                AND booth_id IS NULL''',
                (employee['id'], event_id)).fetchone()
            
            if role_row:
                return jsonify(error='can_not_assign_manager_to_booths'), 400

            cur.execute(
                f'''
                DELETE FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s''',
                (employee['id'], event_id))

            if booth_ids:
                # role se doplní sama v db
                # [('emp_id', 'event_id', 'booth_id_1'), ('emp_id', 'event_id', 'booth_id_2'),...]
                rows = [(employee['id'], event_id, booth_id) for booth_id in booth_ids]

                # "(%s,%s,%s),(%s,%s,%s),..."
                placeholders = ','.join(['(%s,%s,%s)'] * len(rows))
                # ['emp_id', 'event_id', 'booth_id_1', 'emp_id', 'event_id', 'booth_id_2', ...]
                params = [item for row in rows for item in row]

                cur.execute(
                    f'''
                    INSERT INTO employee_event_booth_roles
                    (employee_id, event_id, booth_id)
                    VALUES {placeholders}
                    ''',
                    params)

    return jsonify(), 200


@api_employees_bp.route('/unassign', methods=('POST',))
def unassign_employee_or_manager():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403
    
    try:
        id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not id:
        return jsonify(error='missing_id'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'''
                DELETE FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s''',
                (id, event_id))

    return jsonify(), 200


api_products_bp = Blueprint('products', __name__, url_prefix='/products')
api_bp.register_blueprint(api_products_bp)


@api_products_bp.route('/create', methods=('POST',))
def add_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400
    
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    image_file = request.files.get('image')
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except ValueError:
        return jsonify(error='invalid_booth_id'), 400
    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except ValueError:
        return jsonify(error='invalid_category_id'), 400

    
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

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    params = {
        'event_id': event_id
        }

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if not price:
        return jsonify(error='missing_price'), 400

    ok, errors = validate_product_price(price)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['price'] = price
    
    if request.content_length is not None and request.content_length > current_app.config['MAX_CONTENT_LENGTH']:
        return jsonify(error="file_too_large"), 413

    if image_file:
        safe_filename = secure_filename(image_file.filename)

        if not image_extension_is_allowed(safe_filename):
            return jsonify(error='disallowed_image_extension'), 400
        
        image_is_ok, image_info = verify_image_file_get_info(image_file)
        if not image_is_ok:
            return jsonify(error='image_file_is_invalid'), 400

        dest_dir = current_app.config.get('UPLOAD_FOLDER')
        try:
            saved_name = save_unique_stream(image_file, dest_dir, safe_filename)
        except (PermissionError, OSError, RuntimeError):
            return jsonify(error='unable_to_save_file'), 500
        except RequestEntityTooLarge:
            return jsonify(error="file_too_large"), 413

        params['image_path'] = f'images/products/{saved_name}'
        params['image_filename'] = saved_name
        params['image_mime_type'] = image_info['mime_type']
        params['image_size_bytes'] = os.path.getsize(os.path.join(dest_dir, saved_name))
        params['image_width'] = image_info['width']
        params['image_height'] = image_info['height']
        params['image_alt_text'] = name

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                product_id = cur.execute(
                    f'''
                    INSERT INTO products
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    RETURNING id''',
                    params).fetchone()['id']
                
                if booth_ids:
                    rows = [(product_id, booth_id) for booth_id in booth_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO product_booth_link
                        (product_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params)
                if category_ids:
                    rows = [(product_id, category_id) for category_id in category_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_product_link
                        (product_id, category_id)
                        VALUES {placeholders}
                        ''',
                        params)
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_products_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_products_bp.route('/edit', methods=('POST',))
def edit_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    # try:
    #     event_id = UUID(request.form.get('event-id'))
    # except ValueError:
    #     return jsonify(error='invalid_event_id'), 400

    # if not event_id:
    #     return jsonify(error='missing_event_id'), 400

    try:
        product_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not product_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            product = cur.execute(
                f'''
                SELECT event_id, image_path
                FROM products
                WHERE id = %s''',
                (product_id,)).fetchone()

    if not product:
        return jsonify(error='product_not_found'), 404
    
    event_id = product['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    image_file = request.files.get('image')
    remove_current_image = request.form.get('remove-curent-image')
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except ValueError:
        return jsonify(error='invalid_booth_id'), 400
    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except ValueError:
        return jsonify(error='invalid_category_id'), 400

    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:                        
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

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    if not price:
        return jsonify(error='missing_price'), 400

    ok, errors = validate_product_price(price)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['price'] = price
    
    if request.content_length is not None and request.content_length > current_app.config['MAX_CONTENT_LENGTH']:
        return jsonify(error="file_too_large"), 413
    
    if remove_current_image and not image_file:
        params['image_path'] = None
        params['image_filename'] = None
        params['image_mime_type'] = None
        params['image_size_bytes'] = None
        params['image_width'] = None
        params['image_height'] = None
        params['image_alt_text'] = None

    if image_file:
        safe_filename = secure_filename(image_file.filename)

        if not image_extension_is_allowed(safe_filename):
            return jsonify(error='disallowed_image_extension'), 400
        
        image_is_ok, image_info = verify_image_file_get_info(image_file)
        if not image_is_ok:
            return jsonify(error='image_file_is_invalid'), 400

        dest_dir = current_app.config.get('UPLOAD_FOLDER')
        try:
            saved_name = save_unique_stream(image_file, dest_dir, safe_filename)
        except (PermissionError, OSError, RuntimeError):
            return jsonify(error='unable_to_save_file'), 500
        except RequestEntityTooLarge:
            return jsonify(error="file_too_large"), 413

        params['image_path'] = f'images/products/{saved_name}'
        params['image_filename'] = saved_name
        params['image_mime_type'] = image_info['mime_type']
        params['image_size_bytes'] = os.path.getsize(os.path.join(dest_dir, saved_name))
        params['image_width'] = image_info['width']
        params['image_height'] = image_info['height']
        params['image_alt_text'] = name

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = product_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    UPDATE products
                    SET {col_updates_str}
                    WHERE id = %(id)s''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {product_id}')
                
                cur.execute(
                    f'''
                    DELETE FROM product_booth_link
                    WHERE product_id = %s''',
                    (product_id,))
                
                cur.execute(
                    f'''
                    DELETE FROM category_product_link
                    WHERE product_id = %s''',
                    (product_id,))
                
                if booth_ids:
                    rows = [(product_id, booth_id) for booth_id in booth_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO product_booth_link
                        (product_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params)
                if category_ids:
                    rows = [(product_id, category_id) for category_id in category_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_product_link
                        (product_id, category_id)
                        VALUES {placeholders}
                        ''',
                        params)
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_products_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for product id %s', product_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='product_not_found'), 404
    
    # odstraň předchozí obrázek
    if (remove_current_image or image_file) and product['image_path']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                number_of_image_uses = len(cur.execute(
                    '''
                    SELECT image_path
                    FROM products
                    WHERE image_path = %s''',
                    (product['image_path'],)).fetchall())
        if number_of_image_uses == 0:

            previous_image_path = os.path.join(current_app.static_folder, product['image_path'])

            if os.path.exists(previous_image_path):
                os.remove(previous_image_path)

    return jsonify(), 200


@api_products_bp.route('/delete', methods=('DELETE',))
def delete_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        product_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not product_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            product = cur.execute(
                f'''
                SELECT event_id, image_path
                FROM products
                WHERE id = %s''',
                (product_id,)).fetchone()

    if not product:
        return jsonify(error='product_not_found'), 404
    
    event_id = product['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    DELETE FROM products
                    WHERE id = %s''',
                    (product_id,))
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {product_id}')
                
                # měly by se dít sami:
                cur.execute(
                    f'''
                    DELETE FROM product_booth_link
                    WHERE product_id = %s''',
                    (product_id,))
                cur.execute(
                    f'''
                    DELETE FROM category_product_link
                    WHERE product_id = %s''',
                    (product_id,))
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for product id %s', product_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='product_not_found'), 404
    
    # odstraň předchozí obrázek
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            number_of_image_uses = len(cur.execute(
                '''
                SELECT image_path
                FROM products
                WHERE image_path = %s''',
                (product['image_path'],)).fetchall())
            
    if number_of_image_uses == 0:

        previous_image_path = os.path.join(current_app.static_folder, product['image_path'])

        if os.path.exists(previous_image_path):
            os.remove(previous_image_path)

    return jsonify(), 200


api_categories_bp = Blueprint('categories', __name__, url_prefix='/categories')
api_bp.register_blueprint(api_categories_bp)


@api_categories_bp.route('/create', methods=('POST',))
def add_category():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except ValueError:
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400
    
    name = request.form.get('name', '').strip()
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except ValueError:
        return jsonify(error='invalid_booth_id'), 400
    
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

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    params = {
        'event_id': event_id
        }

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                category_id = cur.execute(
                    f'''
                    INSERT INTO categories
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    RETURNING id''',
                    params).fetchone()['id']
                
                if booth_ids:
                    rows = [(category_id, booth_id) for booth_id in booth_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params)
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_categories_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@api_categories_bp.route('/edit', methods=('POST',))
def edit_category():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        category_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not category_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            category = cur.execute(
                f'''
                SELECT event_id
                FROM categories
                WHERE id = %s''',
                (category_id,)).fetchone()

    if not category:
        return jsonify(error='category_not_found'), 404
    
    event_id = category['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    
    name = request.form.get('name', '').strip()
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except ValueError:
        return jsonify(error='invalid_booth_id'), 400
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:                        
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

    params = {}

    if not name:
        return jsonify(error='missing_name'), 400

    ok, errors = validate_product_or_category_name(name)
    if not ok:
        return jsonify(error=errors[0]), 400
    params['name'] = name

    col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

    params['id'] = category_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    UPDATE categories
                    SET {col_updates_str}
                    WHERE id = %(id)s''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {category_id}')
                
                cur.execute(
                    f'''
                    DELETE FROM category_booth_link
                    WHERE category_id = %s''',
                    (category_id,))
                
                if booth_ids:
                    rows = [(category_id, booth_id) for booth_id in booth_ids]

                    placeholders = ','.join(['(%s,%s)'] * len(rows))

                    params = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params)
    except IntegrityError as e:
        # jméno už existuje: detail obsahuje unique_index_categories_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for category id %s', category_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='category_not_found'), 404

    return jsonify(), 200



@api_categories_bp.route('/delete', methods=('DELETE',))
def delete_category():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        cateogry_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400
    
    if not cateogry_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            category = cur.execute(
                f'''
                SELECT event_id
                FROM categories
                WHERE id = %s''',
                (cateogry_id,)).fetchone()

    if not category:
        return jsonify(error='category_not_found'), 404
    
    event_id = category['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    DELETE FROM categories
                    WHERE id = %s''',
                    (cateogry_id,))
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {cateogry_id}')
                
                # měly by se dít sami:
                cur.execute(
                    f'''
                    DELETE FROM category_booth_link
                    WHERE category_id = %s''',
                    (cateogry_id,))
                cur.execute(
                    f'''
                    DELETE FROM category_product_link
                    WHERE category_id = %s''',
                    (cateogry_id,))
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for category id %s', cateogry_id)
        return jsonify(error='internal_server_error'), 500
    
    if rows_affected == 0:
        return jsonify(error='category_not_found'), 404

    return jsonify(), 200
