import os
import time
from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from psycopg.errors import ForeignKeyViolation
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price, image_extension_is_allowed, verify_image_file_get_info, save_unique_stream, convert_image_paths_from_relative
from cashier_app.utils.employees_users import is_manager
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


def remove_image_if_exists(path):
    if not path or not os.path.exists(path):
        return True
    
    # Retry logic for Windows file locking
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            os.remove(path)
            return True
        except PermissionError:
            if attempt < max_attempts - 1:
                time.sleep(0.1)
            else:
                current_app.logger.warning('failed to remove image %s after %d attempts', path, max_attempts)
        except OSError:
            current_app.logger.warning('failed to remove image %s', path)
            return False
    return False


def delete_unused_images():
    rows_failed_to_delete_img = []
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            unused_image_rows = cur.execute(
                '''
                DELETE FROM product_images AS img
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM products AS p
                    WHERE p.image_id = img.id
                )
                RETURNING img.image_path, 0 AS attempt''',
                ).fetchall()
            unused_image_rows += cur.execute(
                '''
                DELETE FROM product_images_failed_to_delete
                RETURNING image_path, attempt''',
                ).fetchall()
    for image_row_to_delete in unused_image_rows:
        unused_image_path = os.path.join(current_app.static_folder, image_row_to_delete['image_path'])

        success = remove_image_if_exists(unused_image_path)

        if not success:
            if image_row_to_delete['attempt'] < 5:
                rows_failed_to_delete_img.append(image_row_to_delete)
            else:
                current_app.logger.exception('failed to delete image %s after %s requests', image_row_to_delete['attempt'], image_row_to_delete['attempt'])
    
    if rows_failed_to_delete_img:
        placeholders = ",".join(["(%s, %s)"] * len(rows_failed_to_delete_img))
        params = [val for row in rows_failed_to_delete_img 
                for val in (row['image_path'], row['attempt'] + 1)]

        # jestli nešel smazat obrázek, tak vytvoř řadu, aby se smazal příště
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO product_images_failed_to_delete
                    (image_path, attempt)
                    VALUES {placeholders}''',
                    params)


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
                AND link.event_id = %s
                GROUP BY em.id
                ORDER BY em.created_at''',
                (event_id,)).fetchall()
            
            # i need to show and allow uploads/changes of images on the frontend
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
                        ) FILTER (WHERE cat_link.category_id IS NOT NULL),
                        '[]'
                    ) AS categories
                FROM products as p
                LEFT JOIN product_images AS img ON img.id = p.image_id
                LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN booths ON booths.id = bo_link.booth_id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE p.event_id = %s
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
                        ) FILTER (WHERE bo_link.booth_id IS NOT NULL AND booths.deleted_at IS NULL),
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

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except ValueError:
        return jsonify(error='invalid_product_id'), 400

    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except ValueError:
        return jsonify(error='invalid_category_id'), 400

    if booth_type == 'cashier' and (product_ids or category_ids):
        return jsonify(error='cashier_cannot_have_products_or_categories'), 400

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

    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                booth_id = cur.execute(
                    f'''
                    INSERT INTO booths
                    ({cols_str})
                    VALUES ({col_values_placeholders})
                    RETURNING id''',
                    params).fetchone()['id']
                

                if product_ids:
                    rows = [(product_id, booth_id) for product_id in product_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO product_booth_link
                        (product_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)

                if category_ids:
                    rows = [(category_id, booth_id) for category_id in category_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]
                    
                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
    except IntegrityError as e:
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
            booth = cur.execute(
                f'''
                SELECT event_id, booth_type
                FROM booths
                WHERE id = %s
                AND deleted_at IS NULL''',
                (booth_id,)).fetchone()

    if not booth:
        return jsonify(error='booth_not_found'), 404
    
    event_id = booth['event_id']
    booth_type = booth['booth_type']

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

    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except ValueError:
        return jsonify(error='invalid_product_id'), 400

    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except ValueError:
        return jsonify(error='invalid_category_id'), 400

    if booth_type == 'cashier' and (product_ids or category_ids):
        return jsonify(error='cashier_cannot_have_products_or_categories'), 400

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
                
                # Delete existing product and category links
                cur.execute(
                    '''
                    DELETE FROM product_booth_link
                    WHERE booth_id = %s''',
                    (booth_id,))
                
                cur.execute(
                    '''
                    DELETE FROM category_booth_link
                    WHERE booth_id = %s''',
                    (booth_id,))
                
                # Insert new product links
                if product_ids:
                    rows = [(product_id, booth_id) for product_id in product_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]
                    
                    cur.execute(
                        f'''
                        INSERT INTO product_booth_link
                        (product_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
                
                # Insert new category links
                if category_ids:
                    rows = [(category_id, booth_id) for category_id in category_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]
                    
                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
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


@api_booths_bp.route('/products-categories')
def get_products_and_categories():
    """Vrátí produkty a kategorie dostupné pro vybraný stánek.


    Sloučí informace z tabulek link, product_event_prices, products a product_images
    a získá seznam vybraných kategorií (categories), které se vrátí.
    """
    employee = load_logged_in_employee()
    event = load_selected_event()
    booth = load_selected_booth()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if event is None:
        return jsonify(error='no_selected_event'), 400

    if booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            products = cur.execute(
                '''
                SELECT p.id, p.name, p.price, img.image_path,
                  COALESCE(jsonb_agg(
                      DISTINCT jsonb_build_object('name', cat.name)
                      ) FILTER (WHERE cat_link.category_id IS NOT NULL),
                      '[]'
                  ) AS categories
                FROM products AS p
                LEFT JOIN product_images AS img ON img.id = p.image_id
                JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE bo_link.booth_id = %s
                GROUP BY p.id, img.id''',
                (booth['id'],)).fetchall()
            
            categories = cur.execute(
                '''
                SELECT cat.name
                FROM categories AS cat
                JOIN category_booth_link AS link ON link.category_id = cat.id
                WHERE link.booth_id = %s''',
                (booth['id'],)).fetchall()
            
    convert_image_paths_from_relative(products)
    
    return jsonify(products=products, categories=categories), 200


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
            
            if not event:
                return jsonify(error='event_not_found'), 400
            
            for booth_id in booth_ids: ##### change this to ANY(%s)
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
    product_images_params = {}

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
    
    if request.content_length is not None and request.content_length > current_app.config.get('MAX_CONTENT_LENGTH'):
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

        product_images_params['image_path'] = f'images/products/{saved_name}'
        product_images_params['image_filename'] = saved_name
        product_images_params['image_mime_type'] = image_info['mime_type']
        product_images_params['image_size_bytes'] = os.path.getsize(os.path.join(dest_dir, saved_name))
        product_images_params['image_width'] = image_info['width']
        product_images_params['image_height'] = image_info['height']
        product_images_params['image_alt_text'] = name

    created_image_path = product_images_params.get('image_path')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                if image_file:
                    product_images_cols_str = ', '.join(product_images_params.keys())
                    product_images_col_values_placeholders = ', '.join([f'%({col})s' for col in product_images_params.keys()])

                    image_id = cur.execute(
                        f'''
                        INSERT INTO product_images
                        ({product_images_cols_str})
                        VALUES ({product_images_col_values_placeholders})
                        RETURNING id''',
                        product_images_params).fetchone()['id']
                    
                    params['image_id'] = image_id

                cols_str = ', '.join(params.keys())
                col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

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
        remove_image_if_exists(os.path.join(current_app.static_folder, created_image_path))
        # jméno už existuje: detail obsahuje unique_index_products_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except:
        remove_image_if_exists(os.path.join(current_app.static_folder, created_image_path))
        raise

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
                SELECT event_id
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
    product_images_params = {}

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
    
    if request.content_length is not None and request.content_length > current_app.config.get('MAX_CONTENT_LENGTH'):
        return jsonify(error="file_too_large"), 413
    
    if remove_current_image and not image_file:
        params['image_id'] = None


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

        product_images_params['image_path'] = f'images/products/{saved_name}'
        product_images_params['image_filename'] = saved_name
        product_images_params['image_mime_type'] = image_info['mime_type']
        product_images_params['image_size_bytes'] = os.path.getsize(os.path.join(dest_dir, saved_name))
        product_images_params['image_width'] = image_info['width']
        product_images_params['image_height'] = image_info['height']
        product_images_params['image_alt_text'] = name

    created_image_path = product_images_params.get('image_path')

    params['id'] = product_id

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                if image_file:
                    product_images_cols_str = ', '.join(product_images_params.keys())
                    product_images_col_values_placeholders = ', '.join([f'%({col})s' for col in product_images_params.keys()])

                    image_id = cur.execute(
                        f'''
                        INSERT INTO product_images
                        ({product_images_cols_str})
                        VALUES ({product_images_col_values_placeholders})
                        RETURNING id''',
                        product_images_params).fetchone()['id']

                    params['image_id'] = image_id

                col_updates_str = ', '.join([f'{k} = %({k})s' for k in params.keys()])

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
                    '''
                    DELETE FROM product_booth_link
                    WHERE product_id = %s''',
                    (product_id,))
                
                cur.execute(
                    '''
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
        remove_image_if_exists(os.path.join(current_app.static_folder, created_image_path))
        # jméno už existuje: detail obsahuje unique_index_products_name
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        remove_image_if_exists(os.path.join(current_app.static_folder, created_image_path))
        current_app.logger.exception('multiple rows updated for product id %s', product_id)
        return jsonify(error='internal_server_error'), 500
    except:
        remove_image_if_exists(os.path.join(current_app.static_folder, created_image_path))
        raise
    
    if rows_affected == 0:
        return jsonify(error='product_not_found'), 404
    
    # odstraň předchozí obrázek (popřípadě ostatní, které nejsou používané)
    if remove_current_image or image_file:
        delete_unused_images()

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
                SELECT event_id
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
    
    # odstraň předchozí obrázek (popřípadě ostatní, které nejsou používané)
    delete_unused_images()

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
    
    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except ValueError:
        return jsonify(error='invalid_product_id'), 400
    
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
                    AND event_id = %s''',
                    (product_id, event_id)).fetchone()
                
                if not product:
                    return jsonify(error='product_not_found'), 400

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
                    params_list = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
                
                if product_ids:
                    rows = [(category_id, product_id) for product_id in product_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_product_link
                        (category_id, product_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
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
    
    product_ids = []
    try:
        for product_id in request.form.getlist('products'):
            product_ids.append(UUID(product_id))
    except ValueError:
        return jsonify(error='invalid_product_id'), 400
    
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
                    AND event_id = %s''',
                    (product_id, event_id)).fetchone()
                
                if not product:
                    return jsonify(error='product_not_found'), 400

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
                
                cur.execute(
                    f'''
                    DELETE FROM category_product_link
                    WHERE category_id = %s''',
                    (category_id,))
                
                if booth_ids:
                    rows = [(category_id, booth_id) for booth_id in booth_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_booth_link
                        (category_id, booth_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
                
                if product_ids:
                    rows = [(category_id, product_id) for product_id in product_ids]
                    placeholders = ','.join(['(%s,%s)'] * len(rows))
                    params_list = [item for row in rows for item in row]

                    cur.execute(
                        f'''
                        INSERT INTO category_product_link
                        (category_id, product_id)
                        VALUES {placeholders}
                        ''',
                        params_list)
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


@api_bp.route('/<event_id>/statistics', methods=('GET',))
def get_event_statistics(event_id):
    """
    Získá kompletní statistiky pro danou akci.
    Vrací data o:
    - Celkových transakcích
    - Transakcích podle stánků
    - Transakcích podle produktů
    - Časovém rozložení transakcí
    """
    logged_employee = load_logged_in_employee()
    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = str(event_id).strip()
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    # Kontrola oprávnění
    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Kontrola existence akce
            event = cur.execute(
                '''
                SELECT id, name, start_at, end_at, created_at
                FROM events
                WHERE id = %s AND deleted_at IS NULL
                ''',
                (event_id,)
            ).fetchone()

            if not event:
                return jsonify(error='event_not_found'), 404

            # 1. CELKOVÉ STATISTIKY AKCE
            overall_stats = cur.execute(
                '''
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(DISTINCT wallet_id) as unique_wallets,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(CASE WHEN transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN transaction_type = 'refund' THEN 1 ELSE 0 END) as refund_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as total_revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as total_deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as total_withdrawals_czk,
                    SUM(CASE WHEN transaction_type = 'refund' THEN amount_czk ELSE 0 END) as total_refunds_czk
                FROM transactions
                WHERE event_id = %s
                ''',
                (event_id,)
            ).fetchone()

            # 2. STATISTIKY PODLE STÁNKŮ
            booth_stats = cur.execute(
                '''
                SELECT 
                    b.id as booth_id,
                    b.name as booth_name,
                    b.booth_type,
                    COUNT(t.id) as transaction_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN t.transaction_type = 'refund' THEN 1 ELSE 0 END) as refund_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN -t.amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk > 0 THEN t.amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk < 0 THEN -t.amount_czk ELSE 0 END) as withdrawals_czk,
                    SUM(CASE WHEN t.transaction_type = 'refund' THEN t.amount_czk ELSE 0 END) as refunds_czk
                FROM booths b
                LEFT JOIN transactions t ON t.booth_id = b.id
                WHERE b.event_id = %s AND b.deleted_at IS NULL
                GROUP BY b.id, b.name, b.booth_type
                ORDER BY revenue_czk DESC NULLS LAST
                ''',
                (event_id,)
            ).fetchall()

            # 3. STATISTIKY PODLE PRODUKTŮ
            # Extrahujeme produkty z products_info JSON pole v transakcích
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

            # 4. ČASOVÉ ROZLOŽENÍ TRANSAKCÍ (po hodinách)
            hourly_stats = cur.execute(
                '''
                SELECT 
                    DATE_TRUNC('hour', occurred_at) as hour,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk
                FROM transactions
                WHERE event_id = %s
                GROUP BY DATE_TRUNC('hour', occurred_at)
                ORDER BY hour ASC
                ''',
                (event_id,)
            ).fetchall()

            # 5. DENNÍ STATISTIKY
            daily_stats = cur.execute(
                '''
                SELECT 
                    DATE_TRUNC('day', occurred_at) as day,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as withdrawals_czk
                FROM transactions
                WHERE event_id = %s
                GROUP BY DATE_TRUNC('day', occurred_at)
                ORDER BY day ASC
                ''',
                (event_id,)
            ).fetchall()

            # 6. TOP 10 PRODUKTŮ podle tržeb
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

            # 7. STATISTIKY O PENĚŽENKÁCH
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

            # 8. STATISTIKY PRODUKTŮ PODLE STÁNKŮ
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
            'refund_count': overall_stats['refund_count'] or 0,
            'total_revenue_czk': overall_stats['total_revenue_czk'] or 0,
            'total_deposits_czk': overall_stats['total_deposits_czk'] or 0,
            'total_withdrawals_czk': overall_stats['total_withdrawals_czk'] or 0,
            'total_refunds_czk': overall_stats['total_refunds_czk'] or 0
        },
        booth_statistics=[{
            'booth_id': b['booth_id'],
            'booth_name': b['booth_name'],
            'booth_type': b['booth_type'],
            'transaction_count': b['transaction_count'] or 0,
            'payment_count': b['payment_count'] or 0,
            'balance_change_count': b['balance_change_count'] or 0,
            'refund_count': b['refund_count'] or 0,
            'revenue_czk': b['revenue_czk'] or 0,
            'deposits_czk': b['deposits_czk'] or 0,
            'withdrawals_czk': b['withdrawals_czk'] or 0,
            'refunds_czk': b['refunds_czk'] or 0
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
