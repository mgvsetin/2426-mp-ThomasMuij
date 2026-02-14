from pathlib import Path
from flask import Blueprint, current_app, jsonify, url_for, request
from uuid import UUID
from psycopg import IntegrityError
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price, save_image_get_params
from cashier_app.errors import MultipleRowsAffectedError, NoRowsAffectedError
from cashier_app.utils.query_builder import build_insert_statement, build_update_statement, build_delete_statement
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.cascade_capture import capture_product_cascade, convert_dict_to_serializable
from cashier_app.utils.link_sync import sync_product_booth_links, sync_product_category_links
from cashier_app.utils.images import remove_image_if_exists
from cashier_app.utils.general import get_constraint_name

api_products_bp = Blueprint('products', __name__, url_prefix='/products')


@api_products_bp.route('/create', methods=('POST',))
def add_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = UUID(request.form.get('event-id'))
    except (ValueError, TypeError):
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
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400
    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_category_id'), 400

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

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
        result = save_image_get_params(image_file)

        if 'error' in result:
            return jsonify(error=result['error']), result['code']
        product_images_params = result

    created_image_path = product_images_params.get('image_path')

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

                for category_id in category_ids:
                    category = cur.execute(
                        '''
                        SELECT 1
                        FROM categories
                        WHERE id = %s
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (category_id, event_id)).fetchone()

                    if not category:
                        return jsonify(error='category_not_found'), 400

                changes = []

                if image_file:
                    img_sql, img_query_params = build_insert_statement('product_images', product_images_params, returning=['id'])
                    image_id = cur.execute(img_sql, img_query_params).fetchone()['id']
                    params['image_id'] = image_id

                sql, query_params = build_insert_statement('products', params, returning='*')
                new_product = cur.execute(sql, query_params).fetchone()
                product_id = new_product['id']

                changes.append({
                    'table': 'products',
                    'old_values': None,
                    'new_values': convert_dict_to_serializable(dict(new_product))
                })

                changes.extend(sync_product_booth_links(cur, product_id, booth_ids))
                changes.extend(sync_product_category_links(cur, product_id, category_ids))

                save_change(cur, changes, logged_employee['id'])
    except IntegrityError as e:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))

        constraint = get_constraint_name(e)

        if constraint == 'unique_index_products_event_id_name_active':
            return jsonify(error='product_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))
        raise

    return jsonify(), 200


@api_products_bp.route('/edit', methods=('POST',))
def edit_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        product_id = UUID(request.form.get('id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not product_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            product = cur.execute(
                '''
                SELECT event_id
                FROM products
                WHERE id = %s
                AND deleted_at IS NULL''',
                (product_id,)).fetchone()

    if not product:
        return jsonify(error='product_not_found'), 404

    event_id = product['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    image_file = request.files.get('image')
    remove_current_image = request.form.get('remove-curent-image')
    booth_ids = []
    try:
        for booth_id in request.form.getlist('booths'):
            booth_ids.append(UUID(booth_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_booth_id'), 400
    category_ids = []
    try:
        for category_id in request.form.getlist('categories'):
            category_ids.append(UUID(category_id))
    except (ValueError, TypeError):
        return jsonify(error='invalid_category_id'), 400

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
        result = save_image_get_params(image_file)

        if 'error' in result:
            return jsonify(error=result['error']), result['code']
        product_images_params = result

    created_image_path = product_images_params.get('image_path')

    try:
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
                        AND event_id = %s
                        AND deleted_at IS NULL''',
                        (category_id, event_id)).fetchone()

                    if not category:
                        return jsonify(error='category_not_found'), 400

                changes = []

                old_product = cur.execute(
                    'SELECT * FROM products WHERE id = %s AND deleted_at IS NULL',
                    (product_id,)
                ).fetchone()
                if not old_product:
                    raise NoRowsAffectedError()
                old_values = convert_dict_to_serializable(dict(old_product))

                if image_file:
                    img_sql, img_query_params = build_insert_statement('product_images', product_images_params, returning=['id'])
                    image_id = cur.execute(img_sql, img_query_params).fetchone()['id']
                    params['image_id'] = image_id

                sql, query_params = build_update_statement('products', params, product_id, returning='*')

                new_product = cur.execute(sql, query_params).fetchone()

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                new_values = convert_dict_to_serializable(dict(new_product))

                changes.append({
                    'table': 'products',
                    'old_values': old_values,
                    'new_values': new_values
                })

                changes.extend(sync_product_booth_links(cur, product_id, booth_ids))
                changes.extend(sync_product_category_links(cur, product_id, category_ids))

                save_change(cur, changes, logged_employee['id'])

    except IntegrityError as e:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))

        constraint = get_constraint_name(e)

        if constraint == 'unique_index_products_event_id_name_active':
            return jsonify(error='product_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400
    except MultipleRowsAffectedError:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))
        current_app.logger.exception('multiple rows updated for product id %s', product_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))
        return jsonify(error='product_not_found'), 404
    except:
        if created_image_path:
            remove_image_if_exists(Path(current_app.config['UPLOAD_FOLDER'], created_image_path))
        raise

    return jsonify(), 200


@api_products_bp.route('/delete', methods=('DELETE',))
def delete_product():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        product_id = UUID(request.form.get('id'))
    except (ValueError, TypeError):
        return jsonify(error='invalid_id'), 400

    if not product_id:
        return jsonify(error='missing_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            product = cur.execute(
                '''
                SELECT event_id
                FROM products
                WHERE id = %s
                AND deleted_at IS NULL''',
                (product_id,)).fetchone()

    if not product:
        return jsonify(error='product_not_found'), 404

    event_id = product['event_id']

    if not logged_employee['is_admin'] and not is_manager(logged_employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    sql, query_params = build_delete_statement('products', product_id)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                changes = capture_product_cascade(cur, product_id)

                if not changes:
                    raise NoRowsAffectedError()

                cur.execute(sql, query_params)

                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise MultipleRowsAffectedError()
                if rows_affected == 0:
                    raise NoRowsAffectedError()

                sync_product_booth_links(cur, product_id, [])
                sync_product_category_links(cur, product_id, [])

                save_change(cur, changes, logged_employee['id'])
    except MultipleRowsAffectedError:
        current_app.logger.exception('multiple rows deleted for product id %s', product_id)
        return jsonify(error='internal_server_error'), 500
    except NoRowsAffectedError:
        return jsonify(error='product_not_found'), 404

    return jsonify(), 200
