from typing import Sequence, Tuple, Any
import os
from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
import uuid
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


class ForbiddenError(Exception):
    pass

class canNotMakeNewEventIfNotCopyingEvent(Exception):
    pass

class noValidEmployeesToCopy(Exception):
    pass


def change_keys_make_values_UUID(from_dict: dict[str, list[str]], old_to_new_keys_dict: dict[str, str]):
    new_dict = {}
    for old_key, new_key in old_to_new_keys_dict.items():
        new_dict[new_key] = [UUID(id) for id in from_dict[old_key]]
    return new_dict


def make_unique_name(original_name: str, other_names_lower: set[str]) -> str:
    new_name = original_name
    i = 0
    while new_name.lower() in other_names_lower:
        i += 1
        new_name = f"{original_name}_copy" if i == 1 else f"{original_name}_copy{i}"
    
    return new_name


def get_placeholders_and_params(rows: Sequence[Tuple[Any, ...]]) -> Tuple[str, list]:
    """
    Build SQL multi-row placeholders and a flat params list.

    Example:
      rows = [(1, 'a'), (2, 'b')]
      -> placeholders = '(%s,%s),(%s,%s)'
         params = [1, 'a', 2, 'b']

    Returns:
      (placeholders_string, flat_params_list)
    """
    # handle empty input
    if not rows:
        return "", []

    # ensure every row has same length
    row_len = len(rows[0])
    if any(len(row) != row_len for row in rows):
        raise ValueError("All rows must have the same number of columns")

    placeholders_for_row = "(" + ",".join(["%s"] * row_len) + ")"
    placeholders = ",".join([placeholders_for_row] * len(rows))
    params = [item for row in rows for item in row]

    return placeholders, params


api_bp = Blueprint('paste_api', __name__, url_prefix='/api/paste')


@api_bp.route('', methods=('POST',))
def paste():

    # if target is new events, then i need to make the items only from one event every time

    logged_employee = load_logged_in_employee() ######## do more validation

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not request.is_json:
        return jsonify(error='invalid_mimetype'), 400

    data : dict | None = request.get_json(silent=True)

    if data is None:
        return jsonify(error='invalid_request_body'), 400
    
    frontend_targets = data.get('targets') # to event, new event, a booth (cant copy to employees)

    if not frontend_targets:
        return jsonify(error='missing_targets'), 400
    
    if frontend_targets in ['newEvents', 'newEmployees'] and not logged_employee['is_admin']:
        return jsonify(error='insufficient_priviliges'), 403

    targets_are_new_employees = False
    targets_are_new_events = False
    target_ids = {
        'event_ids': [],
        'booth_ids': []
    }

    if frontend_targets == 'newEmployees':
        targets_are_new_employees = True
    elif frontend_targets == 'newEvents':
        targets_are_new_events = True
    else:
        if not isinstance(frontend_targets, dict):
            return jsonify(error='invalid_targets'), 400
        
        frontend_targets_keys = frontend_targets.keys()
        if ('eventIds' not in frontend_targets_keys
            and 'boothIds' not in frontend_targets_keys):
            return jsonify(error='invalid_targets'), 400

        if (not isinstance(frontend_targets['eventIds'], (list, tuple, set))
            or not isinstance(frontend_targets['boothIds'], (list, tuple, set))):
            return jsonify(error='invalid_targets'), 400

        try:
            target_ids = change_keys_make_values_UUID(frontend_targets, {'eventIds': 'event_ids', 'boothIds': 'booth_ids'})
        except (ValueError, TypeError):
            return jsonify(error='invalid_targets'), 400
        
    frontend_data_to_copy = data.get('dataToCopy')

    if not frontend_data_to_copy:
        return jsonify(error='no_data_to_copy'), 400
    
    if not isinstance(frontend_data_to_copy, dict):
        return jsonify(error='invalid_data_to_copy'), 400

    data_to_copy_keys = frontend_data_to_copy.keys()
    if ('eventIds' not in data_to_copy_keys
        and 'boothIds' not in data_to_copy_keys
        and 'productIds' not in data_to_copy_keys
        and 'categoryIds' not in data_to_copy_keys
        and 'managerIds' not in data_to_copy_keys
        and 'employeeIds' not in data_to_copy_keys):
        return jsonify(error='invalid_data_to_copy'), 400
    
    if (not isinstance(frontend_data_to_copy['eventIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['boothIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['productIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['categoryIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['managerIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['employeeIds'], (list, tuple, set))):
        return jsonify(error='invalid_data_to_copy'), 400

    try:
        data_to_copy = change_keys_make_values_UUID(frontend_targets, {
            'eventIds': 'event_ids',
            'boothIds': 'booth_ids',
            'productIds': 'product_ids',
            'categoryIds': 'category_ids',
            'managerIds': 'manager_ids',
            'employeeIds': 'employee_ids'})
    except (ValueError, TypeError):
        return jsonify(error='invalid_data_to_copy'), 400
    

    if targets_are_new_employees:
        if not data_to_copy['employee_ids']:
            return jsonify(error='no_employees_to_copy'), 400
        
        try:
            with get_pool().connection() as conn:
                with conn.cursor() as cur:                
                    employees_to_copy = cur.execute(
                        '''
                        SELECT id, username, email, password_hash, is_admin
                        FROM employees
                        WHERE id = ANY(%s)
                        AND is_admin IS FALSE
                        AND deleted_at IS NULL
                        ''',
                        (data_to_copy['employee_ids'],)).fetchall()
                    
                    if not employees_to_copy:
                        raise noValidEmployeesToCopy()
                    
                    employee_event_booth_roles_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.id, link.employee_id, link.event_id, link.booth_id
                        FROM employee_event_booth_roles AS link
                        JOIN employees AS em ON em.id = link.employee_id
                        JOIN event AS ev ON ev.id = link.event_id
                        LEFT JOIN booths AS bo ON bo.id = link.booth_id
                        WHERE link.employee_id = ANY(%s)
                        AND em.deleted_at IS NULL
                        AND ev.deleted_at IS NULL
                        AND bo.deleted_at IS NULL
                        ''',
                        (data_to_copy['employee_ids'],)).fetchall()
                    
                    employee_unique_columns = cur.execute(
                    '''
                    SELECT username, email
                    FROM employees
                    WHERE deleted_at IS NULL
                    ''',
                    (target_event['id'],)).fetchall()

                    lower_employee_usernames = {emp['username'].lower() for emp in employee_unique_columns}
                    lower_employee_email = {emp['email'].lower() for emp in employee_unique_columns}

                    rows = []
                    copied_to_created_employees = {}
                    
                    for employee_to_copy in employees_to_copy:                        
                        new_employee_username = make_unique_name(employee_to_copy['username'], lower_employee_usernames)
                        lower_employee_usernames.add(new_employee_username.lower())

                        new_employee_email = employee_to_copy['email']
                        i = 0
                        while new_employee_email.lower() in lower_employee_email:
                            before_at_sign, after_at_sign = new_employee_email.split('@')
                            i += 1
                            new_employee_email = f"{before_at_sign}_copy@{after_at_sign}" if i == 1 else f"{before_at_sign}_copy{i}@{after_at_sign}"

                        new_id = uuid.uuid4()
                        copied_to_created_employees[employee_to_copy['id']] = new_id

                        rows.append((
                            new_id,
                            new_employee_username,
                            new_employee_email,
                            employee_to_copy['password_hash'],
                            employee_to_copy['is_admin'],
                            logged_employee['id']
                        ))

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO employees
                            (id, username, email, password_hash, is_admin, created_by)
                            VALUES {placeholders}
                            ''',
                            params)
                        
                    if employee_event_booth_roles_to_copy:
                        rows = [(copied_to_created_employees[link['employee_id']], link['event_id'], link['booth_id']) for link in employee_event_booth_roles_to_copy]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO employee_event_booth_roles
                            (employee_id, event_id, booth_id)
                            VALUES {placeholders}
                            ''',
                            params)
        except noValidEmployeesToCopy:
            return jsonify(error='no_valid_employees_to_copy'), 400

        return jsonify(), 200
    
    target_events = []
    target_booths = []

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                if logged_employee['is_admin']:
                    accessible_events_ids_for_logged_employee = cur.execute(
                    '''
                    SELECT id
                    FROM events
                    WHERE deleted_at IS NULL
                    '''
                ).fetchall()
                else:
                    accessible_events_ids_for_logged_employee = cur.execute(
                        '''
                        SELECT ev.id
                        FROM events AS ev
                        JOIN employee_event_booth_roles AS link ON link.event_id = ev.id
                        WHERE link.employee_id = %s
                        AND link.booth_id IS NULL
                        AND ev.deleted_at IS NULL
                        ''',
                        (logged_employee['id'],)).fetchall()
                
                accessible_events_ids_for_logged_employee = {event['id'] for event in accessible_events_ids_for_logged_employee}

                event_to_copy = []

                if data_to_copy['event_ids']:
                    events_to_copy = cur.execute(
                        '''
                        SELECT
                            ev.id,
                            ev.name,
                            ev.start_at,
                            ev.end_at,

                            -- booths s nested linked_employees, linked_products (s product->categories), linked_categories
                            COALESCE(
                                (
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                    'id', bo.id,
                                    'event_id', bo.event_id,
                                    'name', bo.name,
                                    'booth_type', bo.booth_type,

                                    -- employees propojené s tímto booth
                                    'linked_employees', COALESCE((
                                    SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                        'employee_id', em_bo_link.employee_id,
                                        'booth_id',    em_bo_link.booth_id
                                    ))
                                    FROM employee_event_booth_roles em_bo_link
                                    JOIN employees em2 ON em2.id = em_bo_link.employee_id AND em2.deleted_at IS NULL
                                    WHERE em_bo_link.event_id = ev.id AND em_bo_link.booth_id = bo.id
                                    ), '[]'::jsonb),

                                    -- products propojené s tímto booth, každý produkt má jeho linked_categories
                                    'linked_products', COALESCE((
                                    SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                        'product_id', pr_bo_link.product_id,
                                        'booth_id',   pr_bo_link.booth_id,
                                        'linked_categories', COALESCE((
                                        SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                            'category_id', ca_pr_link.category_id,
                                            'product_id',  ca_pr_link.product_id
                                        ))
                                        FROM category_product_link ca_pr_link
                                        WHERE ca_pr_link.product_id = pr_bo_link.product_id
                                        ), '[]'::jsonb)
                                    ))
                                    FROM product_booth_link pr_bo_link
                                    WHERE pr_bo_link.booth_id = bo.id
                                    ), '[]'::jsonb),

                                    -- categories propojené s tímto booth
                                    'linked_categories', COALESCE((
                                    SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                        'category_id', ca_bo_link.category_id,
                                        'booth_id',    ca_bo_link.booth_id
                                    ))
                                    FROM category_booth_link ca_bo_link
                                    WHERE ca_bo_link.booth_id = bo.id
                                    ), '[]'::jsonb)
                                ))
                                FROM booths bo
                                WHERE bo.event_id = ev.id AND bo.deleted_at IS NULL
                                ), '[]'::jsonb
                            ) AS booths,

                            -- products pro event
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'id', pr.id, 'event_id', pr.event_id, 'name', pr.name, 'price', pr.price,
                                'image_path', pr.image_path, 'image_filename', pr.image_filename,
                                'image_mime_type', pr.image_mime_type, 'image_size_bytes', pr.image_size_bytes,
                                'image_width', pr.image_width, 'image_height', pr.image_height, 'image_alt_text', pr.image_alt_text
                                ))
                                FROM products pr
                                WHERE pr.event_id = ev.id
                            ), '[]'::jsonb) AS products,

                            -- categories pro event
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'id', ca.id, 'event_id', ca.event_id, 'name', ca.name
                                ))
                                FROM categories ca
                                WHERE ca.event_id = ev.id
                            ), '[]'::jsonb) AS categories,

                            -- managers pro event
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'employee_id', em_bo_link.employee_id,
                                'booth_id',    em_bo_link.booth_id
                                ))
                                FROM employee_event_booth_roles em_bo_link
                                JOIN employees em3 ON em3.id = em_bo_link.employee_id AND em3.deleted_at IS NULL
                                WHERE em_bo_link.event_id = ev.id AND em_bo_link.booth_id IS NULL
                            ), '[]'::jsonb) AS managers

                        FROM events ev
                        WHERE ev.id = ANY(%s)
                            AND ev.deleted_at IS NULL;
                        ''',
                        (data_to_copy['event_ids'],)).fetchall()
                
                events_to_copy_ids = [event['id'] for event in events_to_copy]


                for event_id in events_to_copy_ids:
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()


                if targets_are_new_events:
                    if not events_to_copy:
                        raise canNotMakeNewEventIfNotCopyingEvent()

                    lower_all_event_names = cur.execute(
                        '''
                        SELECT name
                        FROM events
                        WHERE deleted_at IS NULL
                        ''',
                        ).fetchall()

                    lower_all_event_names = {event['name'].lower() for event in lower_all_event_names}

                    event_rows = []
                    booth_rows = []
                    product_rows = []
                    category_rows = []

                    copied_to_created_event_ids = {}

                    copied_to_created_booth_ids_for_event_id = {}
                    copied_to_created_product_ids_for_event_id = {}
                    copied_to_created_category_ids_for_event_id = {}

                    for event_to_copy in events_to_copy:
                        copied_to_created_booth_ids_for_event_id[event_to_copy['id']] = {}
                        copied_to_created_product_ids_for_event_id[event_to_copy['id']] = {}
                        copied_to_created_category_ids_for_event_id[event_to_copy['id']] = {}


                        new_event_name = make_unique_name(event_to_copy['name'], lower_all_event_names)
                        lower_all_event_names.add(new_event_name.lower())

                        new_id = uuid.uuid4()
                        copied_to_created_event_ids[event_to_copy['id']] = new_id

                        event_rows.append((
                            new_id,
                            new_event_name,
                            event_to_copy['start_at'],
                            event_to_copy['end_at'],
                            logged_employee['id']
                        ))
                        
                        # unique names nemusíme řešit protože to je nový event

                        for booth in event_to_copy['booths']:
                            new_id = uuid.uuid4()
                            copied_to_created_booth_ids_for_event_id[event_to_copy['id']][booth['id']] = new_id

                            booth_rows.append((
                                new_id,
                                copied_to_created_event_ids[event_to_copy['id']],
                                booth['name'],
                                booth['booth_type'],
                                logged_employee['id']
                            ))

                        for product in event_to_copy['products']:
                            new_id = uuid.uuid4()
                            copied_to_created_product_ids_for_event_id[event_to_copy['id']][product['id']] = new_id

                            product_rows.append((
                                new_id,
                                copied_to_created_event_ids[event_to_copy['id']],
                                product['name'],
                                product['price'],
                                product['image_path'],
                                product['image_filename'],
                                product['image_mime_type'],
                                product['image_size_bytes'],
                                product['image_width'],
                                product['image_height'],
                                product['image_alt_text']
                            ))

                        for category in event_to_copy['categories']:
                            new_id = uuid.uuid4()
                            copied_to_created_category_ids_for_event_id[event_to_copy['id']][category['id']] = new_id

                            category_rows.append((
                                new_id,
                                copied_to_created_event_ids[event_to_copy['id']],
                                category['name']
                            ))

                    placeholders, params = get_placeholders_and_params(event_rows)
                    cur.execute(
                        f'''
                        INSERT INTO events
                        (id, name, start_at, end_at, created_by)
                        VALUES {placeholders}
                        ''',
                        params)
                    
                    placeholders, params = get_placeholders_and_params(booth_rows)
                    cur.execute(
                        f'''
                        INSERT INTO booths
                        (id, event_id, name, booth_type, created_by)
                        VALUES {placeholders}
                        ''',
                        params)
                    
                    placeholders, params = get_placeholders_and_params(product_rows)
                    cur.execute(
                        f'''
                        INSERT INTO products
                        (id, event_id, name, price, image_path, image_filename, image_mime_type, image_size_bytes, image_width, image_height, image_alt_text)
                        VALUES {placeholders}
                        ''',
                        params)
                    
                    placeholders, params = get_placeholders_and_params(category_rows)
                    cur.execute(
                        f'''
                        INSERT INTO categories
                        (id, event_id, name)
                        VALUES {placeholders}
                        ''',
                        params)


                    # spojovací tabulky:
                    employee_event_booth_roles_rows = []
                    
                    for event in events_to_copy:
                        created_event_id = copied_to_created_event_ids[event['id']]
                        copied_to_created_booth_ids = copied_to_created_booth_ids_for_event_id[created_event_id]
                        copied_to_created_product_ids = copied_to_created_product_ids_for_event_id[created_event_id]
                        copied_to_created_category_ids = copied_to_created_category_ids_for_event_id[created_event_id]

                        for manager_row in event['managers']:
                            employee_event_booth_roles_rows.append((
                                manager_row['employee_id'],
                                created_event_id,
                                None
                            ))

                        for booth in event['booths']:
                            for employee_row in booth['linked_employees']:
                                employee_event_booth_roles_rows.append((
                                    employee_row['employee_id'],
                                    created_event_id,
                                    copied_to_created_booth_ids[booth['id']]
                                ))

                                # move the linked categories out of the linked products in booths of copied_event into the general products of copied_event


                    return jsonify(), 200



                target_events = cur.execute(
                    '''
                    SELECT id
                    FROM events
                    WHERE id = ANY(%s)
                    AND deleted_at IS NULL
                    ''',
                    (target_ids,)).fetchall()
                
                target_booths = cur.execute(
                    '''
                    SELECT id, event_id, booth_type
                    FROM booths
                    WHERE id = ANY(%s)
                    AND deleted_at IS NULL
                    ''',
                    (target_ids,)).fetchall()

                for event in target_events:
                    event_id = event['id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                for booth in target_booths:
                    event_id = booth['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                booth_to_copy = []
                
                if data_to_copy['booth_ids']:
                    booths_to_copy = cur.execute(
                        '''
                        SELECT
                            bo.id,
                            bo.event_id,
                            bo.name,
                            bo.booth_type,

                            -- employees propojené s tímto booth
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'employee_id', em_bo_link.employee_id,
                                'booth_id',    em_bo_link.booth_id
                                ))
                                FROM employee_event_booth_roles em_bo_link
                                JOIN employees em2 ON em2.id = em_bo_link.employee_id AND em2.deleted_at IS NULL
                                WHERE em_bo_link.event_id = bo.event_id AND em_bo_link.booth_id = bo.id
                            ), '[]'::jsonb) AS linked_employees,

                            -- products propojené s tímto booth, každý product obsahuje linked_categories
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'product_id', pr_bo_link.product_id,
                                'booth_id',   pr_bo_link.booth_id,
                                'linked_categories', COALESCE((
                                    SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                    'category_id', ca_pr_link.category_id,
                                    'product_id',  ca_pr_link.product_id
                                    ))
                                    FROM category_product_link ca_pr_link
                                    WHERE ca_pr_link.product_id = pr_bo_link.product_id
                                ), '[]'::jsonb)
                                ))
                                FROM product_booth_link pr_bo_link
                                WHERE pr_bo_link.booth_id = bo.id
                            ), '[]'::jsonb) AS linked_products,

                            -- categories propojené s tímto booth
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'category_id', ca_bo_link.category_id,
                                'booth_id',    ca_bo_link.booth_id
                                ))
                                FROM category_booth_link ca_bo_link
                                WHERE ca_bo_link.booth_id = bo.id
                            ), '[]'::jsonb) AS linked_categories

                        FROM booths bo
                        WHERE bo.id = ANY(%s)
                            AND bo.deleted_at IS NULL;
                        ''',
                        (data_to_copy['booth_ids'],)).fetchall()

                booths_to_copy_ids = [booth['id'] for booth in booths_to_copy]

                for booth in booths_to_copy:
                    event_id = booth['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()

                products_to_copy = []
                
                if data_to_copy['product_ids']:
                    products_to_copy = cur.execute(
                        '''
                        SELECT
                            pr.id,
                            pr.event_id,
                            pr.name,
                            pr.price,
                            pr.image_path,
                            pr.image_filename,
                            pr.image_mime_type,
                            pr.image_size_bytes,
                            pr.image_width,
                            pr.image_height,
                            pr.image_alt_text,

                            -- booths propojené s tímto product
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'booth_id', pr_bo_link.booth_id,
                                'product_id',    pr_bo_link.product_id
                                ))
                                FROM product_booth_link pr_bo_link
                                JOIN booths bo ON bo.id = pr_bo_link.booth_id AND bo.deleted_at IS NULL
                                WHERE pr_bo_link.product_id = pr.id

                            ), '[]'::jsonb) AS linked_booths,

                            -- categories propojené s tímto product
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'category_id', ca_pr_link.category_id,
                                'product_id',    ca_pr_link.product_id
                                ))
                                FROM category_product_link ca_pr_link
                                WHERE ca_pr_link.product_id = pr.id
                            ), '[]'::jsonb) AS linked_categories

                        FROM products AS pr
                        WHERE pr.id = ANY(%s)
                        ''',
                        (data_to_copy['product_ids'],)).fetchall()
                
                for product in products_to_copy:
                    event_id = product['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                categories_to_copy = []

                if data_to_copy['category_ids']:
                    categories_to_copy = cur.execute(
                        '''
                        SELECT
                            ca.id,
                            ca.event_id,
                            ca.name,

                            -- booths propojené s touto category
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'booth_id', ca_bo_link.booth_id,
                                'category_id', ca_bo_link.category_id
                                ))
                                FROM category_booth_link ca_bo_link
                                JOIN booths bo ON bo.id = ca_bo_link.booth_id AND bo.deleted_at IS NULL
                                WHERE ca_bo_link.category_id = ca.id

                            ), '[]'::jsonb) AS linked_booths,

                            -- products propojené s touto category
                            COALESCE((
                                SELECT jsonb_agg(DISTINCT jsonb_build_object(
                                'category_id', ca_pr_link.category_id,
                                'product_id',    ca_pr_link.product_id
                                ))
                                FROM category_product_link ca_pr_link
                                WHERE ca_pr_link.category_id = ca.id
                            ), '[]'::jsonb) AS linked_products

                        FROM categories AS ca
                        WHERE ca.id = ANY(%s)
                        ''',
                        (data_to_copy['category_ids'],)).fetchall()
                
                for category in categories_to_copy:
                    event_id = category['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    

                managers_to_copy = []

                if data_to_copy['manager_ids']:
                    managers_to_copy = cur.execute(
                        '''
                        SELECT e.id, link.event_id
                        FROM employee_event_booth_roles AS link
                        JOIN employees AS e ON e.id = link.employee_id
                        WHERE link.employee_id = ANY(%s)
                        AND link.booth_id IS NULL
                        AND e.deleted_at IS NULL
                        ''',
                        (data_to_copy['manager_ids'],)).fetchall()
                
                # make 2 different employees
                # 1 where employee_id = any, the other event_id = any and booth_id = any
                # event and booth just do what they did
                # copying an employee directly copies everything for that employee and just changes names,... to _copy (make sure to do the email in the correct place)
                # maybe dont do the second one though cuz of the name/email uniqueness
                
                # employees_assigned_to_copied_booths_and_events = cur.execute(
                #     '''
                #     SELECT e.id, link.event_id
                #     FROM employee_event_booth_roles AS link
                #     JOIN employees AS e ON e.id = link.employee_id
                #     WHERE (link.event_id = ANY(%s) -- není tady "link.employee_id = ANY()", protože nelze zkopírovat přiřazení ke stánku, bez stánku
                #         OR link.booth_id = ANY(%s))
                #     AND link.booth_id IS NOT NULL
                #     AND e.deleted_at IS NULL
                #     ''',
                # (events_to_copy_ids, booths_to_copy_ids)).fetchall()

                # do the checks so that if the to be manager is already at a booth, it wont do anything (same for reverse), can this be done through on conflict do nothing?
                
                # pouze spojení se stánkama, které jsou zkopírované a teď se vkládají (jestli se kopíruje 
                # event, tak to budou všichni v něm, protože se tím zároveň kopírují všechny stánky)
                # employee_booth_roles_to_copy = cur.execute(
                #     '''
                #     SELECT link.employee_id, link.booth_id
                #     FROM employee_event_booth_roles AS link
                #     JOIN employees AS e ON e.id = link.employee_id
                #     WHERE (link.employee_id = ANY(%s)
                #         AND link.booth_id = ANY(%s))
                #     AND link.booth_id IS NOT NULL
                #     AND e.deleted_at IS NULL
                #     ''',
                #     (data_to_copy_uuids, booths_to_copy_ids)).fetchall()

                # this will only be further down in a for loop of the target_booths, other stuff that can be only linked to an event will be done here
                # and finished down in the for loop same as these employees
                # when adding the products in the for loop, make sure to check whether it was already added before or not
                # or do a left join to include them here
                
                # need separate emp booth roles for copying to event and copying to booth?
                # need separate for all of it?, so do it later in a for loop?
                # but have to do some here bcs some stuff doesnt have to belong to a booth
                
                # finish the employees


                    
                copied_ids_already_created_for_target_event = {}

                copied_to_created_booths = {}
                copied_to_created_products = {}
                copied_to_created_categories = {}


                for target_event in target_events:
                    if (copied_ids_already_created_for_target_event.get(target_event['id']) is None):
                        copied_ids_already_created_for_target_event[target_event['id']] = set()

                    if events_to_copy:
                        for event_to_copy in events_to_copy:
                            pass


                    if booths_to_copy:
                        lower_booth_names_of_target_event = cur.execute(
                        '''
                        SELECT name
                        FROM booths
                        WHERE event_id = %s
                        AND deleted_at IS NULL
                        ''',
                        (target_event['id'],)).fetchall()
                    
                        lower_booth_names_of_target_event = {booth['name'].lower() for booth in lower_booth_names_of_target_event}

                        rows = []
                            
                        for booth_to_copy in booths_to_copy:
                            if targets_are_new_events and booth_to_copy['event_id'] != target_event['id_of_copied_event']:
                                continue

                            if booth_to_copy['id'] in copied_ids_already_created_for_target_event[target_event['id']]:
                                continue
                            copied_ids_already_created_for_target_event[target_event['id']].add(booth_to_copy['id'])

                            new_booth_name = make_unique_name(booth_to_copy['name'], lower_booth_names_of_target_event)
                            lower_booth_names_of_target_event.add(new_booth_name.lower())

                            new_id = uuid.uuid4()
                            copied_to_created_booths[booth_to_copy['id']] = new_id

                            rows.append((
                                new_id,
                                new_booth_name,
                                target_event['id'],
                                booth_to_copy['booth_type'],
                                logged_employee['id']
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            cur.execute(
                                f'''
                                INSERT INTO booths
                                (id, name, event_id, booth_type, created_by)
                                VALUES {placeholders}
                                ''',
                                params)

                    if managers_to_copy:
                        # for manager in managers_to_copy:
                        #     cur.execute(
                        #         '''SELECT 1 FROM employee_event_booth_roles
                        #         WHERE employee_id = %s
                        #         AND event_id = %s''',
                        #         (manager['id'], target_event['id'])).fetchone()

                        rows = []

                        for manager in managers_to_copy:
                            if targets_are_new_events and manager['event_id'] != target_event['id_of_copied_event']:
                                continue

                            if manager['id'] in copied_ids_already_created_for_target_event[target_event['id']]:
                                continue

                            copied_ids_already_created_for_target_event[target_event['id']].add(manager['id'])

                            rows.append((
                                manager['id'],
                                target_event['id'],
                                None
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            # kontrole, že employee není admin nebo je deleted není potřeba, protože data se berou z této tabulky
                            cur.execute(
                                f'''
                                WITH input_data AS (
                                VALUES {placeholders}
                                ),
                                input_with_cols AS (
                                SELECT 
                                    column1::uuid AS employee_id,
                                    column2::uuid AS event_id,
                                    column3::uuid AS booth_id
                                FROM input_data
                                ),
                                valid_rows AS (
                                SELECT i.*
                                FROM input_with_cols i
                                WHERE i.booth_id IS NULL
                                    AND NOT EXISTS (
                                    SELECT 1 FROM employee_event_booth_roles link
                                    WHERE link.employee_id = i.employee_id
                                        AND link.event_id = i.event_id
                                    )
                                )
                                INSERT INTO employee_event_booth_roles (employee_id, event_id, booth_id)
                                SELECT * FROM valid_rows''',
                                params)

                    if products_to_copy:
                        lower_product_names_of_target_event = cur.execute(
                        '''
                        SELECT name
                        FROM products
                        WHERE event_id = %s
                        ''',
                        (target_event['id'],)).fetchall()

                        lower_product_names_of_target_event = {product['name'].lower() for product in lower_product_names_of_target_event}

                        rows = []
                        for product in products_to_copy:
                            if targets_are_new_events and product['event_id'] != target_event['id_of_copied_event']:
                                continue

                            if product['id'] in copied_ids_already_created_for_target_event[target_event['id']]:
                                continue
                            copied_ids_already_created_for_target_event[target_event['id']].add(product['id'])

                            if product['event_id'] == target_event['id'] and product['id'] not in data_to_copy:
                                copied_to_created_products[product['id']] = product['id']
                                continue

                            new_product_name = make_unique_name(product['name'], lower_product_names_of_target_event)
                            lower_product_names_of_target_event.add(new_product_name.lower())

                            new_id = uuid.uuid4()
                            copied_to_created_products[product['id']] = new_id

                            rows.append((
                                new_id,
                                target_event['id'],
                                new_product_name,
                                product['price'],
                                product['image_path'],
                                product['image_filename'],
                                product['image_mime_type'],
                                product['image_size_bytes'],
                                product['image_width'],
                                product['image_height'],
                                product['image_alt_text']
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            cur.execute(
                                f'''
                                INSERT INTO products
                                (id, event_id, name, price, image_path, image_filename, image_mime_type, image_size_bytes, image_width, image_height, image_alt_text)
                                VALUES {placeholders}
                                ''',
                                params)

                    if categories_to_copy:
                        lower_category_names_of_target_event = cur.execute(
                        '''
                        SELECT name
                        FROM categories
                        WHERE event_id = %s
                        ''',
                        (target_event['id'],)).fetchall()

                        lower_category_names_of_target_event = {category['name'].lower() for category in lower_category_names_of_target_event}

                        rows = []
                        for category in categories_to_copy:
                            if targets_are_new_events and category['event_id'] != target_event['id_of_copied_event']:
                                continue

                            if category['id'] in copied_ids_already_created_for_target_event[target_event['id']]:
                                continue
                            copied_ids_already_created_for_target_event[target_event['id']].add(category['id'])

                            if category['event_id'] == target_event['id'] and category['id'] not in data_to_copy:
                                copied_to_created_categories[category['id']] = category['id']
                                continue

                            new_category_name = make_unique_name(category['name'], lower_category_names_of_target_event)
                            lower_category_names_of_target_event.add(new_category_name.lower())

                            new_id = uuid.uuid4()
                            copied_to_created_categories[category['id']] = new_id

                            rows.append((
                                new_id,
                                new_category_name,
                                target_event['id']
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            cur.execute(
                                f'''
                                INSERT INTO categories
                                (id, name, event_id)
                                VALUES {placeholders}
                                ''',
                                params)
                    
                    # vytovření řádků ve spojovacích tabulkách, kde to jde:
                    # booths x employees
                    if targets_are_new_events:
                        employee_booth_roles = cur.execute(
                            '''
                            SELECT booth_id, employee_id, event_id
                            FROM employee_event_booth_roles
                            WHERE booth_id = ANY(%s)
                            AND event_id = %s
                            ''',
                        (list(copied_to_created_booths.keys()), target_event['id_of_copied_event'])).fetchall()
                    else:
                        employee_booth_roles = cur.execute(
                            '''
                            SELECT booth_id, employee_id, event_id
                            FROM employee_event_booth_roles
                            WHERE booth_id = ANY(%s)
                            ''',
                        (list(copied_to_created_booths.keys()),)).fetchall()

                    if employee_booth_roles:
                        rows = [(copied_to_created_booths[row['booth_id']], row['employee_id'], target_event['id']) for row in employee_booth_roles]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            WITH input_data AS (
                            VALUES {placeholders}
                            ),
                            input_with_cols AS (
                            SELECT 
                                column1::uuid AS booth_id,
                                column2::uuid AS employee_id,
                                column3::uuid AS event_id
                            FROM input_data
                            ),
                            valid_rows AS (
                            SELECT i.booth_id, i.employee_id, i.event_id
                            FROM input_with_cols i
                            WHERE i.booth_id IS NOT NULL
                                AND NOT EXISTS (
                                SELECT 1 FROM employee_event_booth_roles link
                                WHERE link.employee_id = i.employee_id
                                    AND link.event_id = i.event_id
                                    AND link.booth_id IS NULL -- already a manager
                                )
                            )
                            INSERT INTO employee_event_booth_roles (booth_id, employee_id, event_id)
                            SELECT booth_id, employee_id, event_id FROM valid_rows
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # booths x products
                    if targets_are_new_events:
                        product_booth_link = cur.execute(
                            '''
                            SELECT DISTINCT link.booth_id, link.product_id
                            FROM product_booth_link AS link
                            JOIN booths AS bo ON bo.id = link.booth_id
                            WHERE link.booth_id = ANY(%s)
                            AND link.product_id = ANY(%s)
                            AND bo.event_id = %s
                            ''',
                            (list(copied_to_created_booths.keys()), list(copied_to_created_products.keys()), target_event['id_of_copied_event'])).fetchall()    
                    else:
                        product_booth_link = cur.execute(
                            '''
                            SELECT DISTINCT link.booth_id, link.product_id, p.event_id
                            FROM product_booth_link AS link
                            JOIN products AS p ON p.id = link.product_id
                            WHERE (link.booth_id = ANY(%s) OR p.event_id = %s)
                            AND link.product_id = ANY(%s)
                            ''',
                            (list(copied_to_created_booths.keys()), target_event['id'], list(copied_to_created_products.keys()))).fetchall()

                    if product_booth_link:
                        rows = []
                        for row in product_booth_link:
                            # do the same thing for categories (sql in else: + this below) (maybe for pro + cat too)
                            if row['event_id'] == target_event['id'] and row['booth_id'] not in copied_to_created_booths:
                                booth_id = row['booth_id']
                            else:
                                booth_id = copied_to_created_booths[row['booth_id']]

                            rows.append((
                                booth_id,
                                copied_to_created_products[row['product_id']]
                            ))

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO product_booth_link
                            (booth_id, product_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # booths x categories
                    if targets_are_new_events:
                        category_booth_link = cur.execute(
                            '''
                            SELECT DISTINCT link.booth_id, link.category_id
                            FROM category_booth_link AS link
                            JOIN booths AS bo ON bo.id = link.booth_id
                            WHERE link.booth_id = ANY(%s)
                            AND link.category_id = ANY(%s)
                            AND bo.event_id = %s
                            ''',
                            (list(copied_to_created_booths.keys()), list(copied_to_created_categories.keys()), target_event['id_of_copied_event'])).fetchall() 
                    else:
                        category_booth_link = cur.execute(
                            '''
                            SELECT booth_id, category_id
                            FROM category_booth_link
                            WHERE booth_id = ANY(%s)
                            AND category_id = ANY(%s)
                            ''',
                            (list(copied_to_created_booths.keys()), list(copied_to_created_categories.keys()))).fetchall() 

                    if category_booth_link:
                        rows = [(copied_to_created_booths[row['booth_id']], copied_to_created_categories[row['category_id']]) for row in category_booth_link]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_booth_link
                            (booth_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # products x categories
                    if targets_are_new_events:
                        category_product_link = cur.execute(
                            '''
                            SELECT DISTINCT link.product_id, link.category_id
                            FROM category_product_link AS link
                            JOIN products AS p ON p.id = link.product_id
                            WHERE link.product_id = ANY(%s)
                            AND link.category_id = ANY(%s)
                            AND p.event_id = %s
                            ''',
                            (list(copied_to_created_products.keys()), list(copied_to_created_categories.keys()), target_event['id_of_copied_event'])).fetchall() 
                    else:
                        category_product_link = cur.execute(
                            '''
                            SELECT product_id, category_id
                            FROM category_product_link
                            WHERE product_id = ANY(%s)
                            AND category_id = ANY(%s)
                            ''',
                            (list(copied_to_created_products.keys()), list(copied_to_created_categories.keys()))).fetchall()

                    if category_product_link:
                        rows = [(copied_to_created_products[row['product_id']], copied_to_created_categories[row['category_id']]) for row in category_product_link]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_product_link
                            (product_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)



                for target_booth in target_booths:
                    if (copied_ids_already_created_for_target_event.get(target_booth['event_id']) is None):
                        copied_ids_already_created_for_target_event[target_booth['event_id']] = set()

                    # should it get created if target booth is a cashier?
                    if products_to_copy:
                        lower_product_names_of_target_event = cur.execute(
                        '''
                        SELECT name
                        FROM products
                        WHERE event_id = %s
                        ''',
                        (target_booth['event_id'],)).fetchall()

                        lower_product_names_of_target_event = {product['name'].lower() for product in lower_product_names_of_target_event}

                        rows = []
                        for product in products_to_copy:
                            if product['id'] in copied_ids_already_created_for_target_event[target_booth['event_id']]:
                                continue
                            copied_ids_already_created_for_target_event[target_booth['event_id']].add(product['id'])

                            if product['event_id'] == target_booth['event_id']:
                                copied_to_created_products[product['id']] = product['id']
                                continue

                            new_product_name = make_unique_name(product['name'], lower_product_names_of_target_event)
                            lower_product_names_of_target_event.add(new_product_name.lower())

                            new_id = uuid.uuid4()
                            copied_to_created_products[product['id']] = new_id

                            rows.append((
                                new_id,
                                target_event['id'],
                                new_product_name,
                                product['price'],
                                product['image_path'],
                                product['image_filename'],
                                product['image_mime_type'],
                                product['image_size_bytes'],
                                product['image_width'],
                                product['image_height'],
                                product['image_alt_text']
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            cur.execute(
                                f'''
                                INSERT INTO products
                                (id, event_id, name, price, image_path, image_filename, image_mime_type, image_size_bytes, image_width, image_height, image_alt_text)
                                VALUES {placeholders}
                                ''',
                                params)

                    if categories_to_copy:
                        lower_category_names_of_target_event = cur.execute(
                        '''
                        SELECT name
                        FROM categories
                        WHERE event_id = %s
                        ''',
                        (target_booth['event_id'],)).fetchall()

                        lower_category_names_of_target_event = {category['name'].lower() for category in lower_category_names_of_target_event}

                        rows = []
                        for category in categories_to_copy:
                            if category['id'] in copied_ids_already_created_for_target_event[target_booth['event_id']]:
                                continue
                            copied_ids_already_created_for_target_event[target_booth['event_id']].add(category['id'])

                            if category['event_id'] == target_booth['event_id']:
                                copied_to_created_categories[category['id']] = category['id']
                                continue

                            new_category_name = make_unique_name(category['name'], lower_category_names_of_target_event)
                            lower_category_names_of_target_event.add(new_category_name.lower())

                            new_id = uuid.uuid4()
                            copied_to_created_categories[category['id']] = new_id

                            rows.append((
                                new_id,
                                new_category_name,
                                target_event['id']
                            ))

                        if rows:
                            placeholders, params = get_placeholders_and_params(rows)

                            cur.execute(
                                f'''
                                INSERT INTO categories
                                (id, name, event_id)
                                VALUES {placeholders}
                                ''',
                                params)
                    
                    # vytovření řádků ve spojovacích tabulkách:
                    # booth x employees
                    if employees_assigned_to_copied_booths_and_events:
                        rows = [(target_booth['id'], row['employee_id'], target_booth['event_id']) for row in employees_assigned_to_copied_booths_and_events]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            WITH input_data AS (
                            VALUES {placeholders}
                            ),
                            input_with_cols AS (
                            SELECT 
                                column1::uuid AS booth_id,
                                column2::uuid AS employee_id,
                                column3::uuid AS event_id
                            FROM input_data
                            ),
                            valid_rows AS (
                            SELECT i.booth_id, i.employee_id, i.event_id
                            FROM input_with_cols i
                            WHERE i.booth_id IS NOT NULL
                                AND NOT EXISTS (
                                SELECT 1 FROM employee_event_booth_roles link
                                WHERE link.employee_id = i.employee_id
                                    AND link.event_id = i.event_id
                                    AND link.booth_id IS NULL -- already a manager
                                )
                            )
                            INSERT INTO employee_event_booth_roles (booth_id, employee_id, event_id)
                            SELECT booth_id, employee_id, event_id FROM valid_rows
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # booth x products
                    if products_to_copy and target_booth['booth_type'] == 'seller':
                        with open('prints.txt', 'a', encoding='utf-8') as f:
                            print(copied_to_created_products, file=f)
                            print(products_to_copy, file=f)
                        rows = [(target_booth['id'], copied_to_created_products[row['id']]) for row in products_to_copy]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO product_booth_link
                            (booth_id, product_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # booths x categories
                    if categories_to_copy and target_booth['booth_type'] == 'seller':
                        rows = [(target_booth['id'], copied_to_created_categories[row['category_id']]) for row in categories_to_copy]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_booth_link
                            (booth_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    # products x categories
                    category_product_link = cur.execute(
                        '''
                        SELECT product_id, category_id
                        FROM category_product_link
                        WHERE product_id = ANY(%s)
                        AND category_id = ANY(%s)
                        ''',
                    (list(copied_to_created_products.keys()), list(copied_to_created_categories.keys()))).fetchall()

                    if category_product_link:
                        rows = [(copied_to_created_products[row['product_id']], copied_to_created_categories[row['category_id']]) for row in category_product_link]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_product_link
                            (product_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
    except ForbiddenError:
        return jsonify(error='insufficient_priviliges'), 403
    except canNotMakeNewEventIfNotCopyingEvent:
        return jsonify(error='can_not_make_new_event_if_not_copying_event'), 400

    return jsonify(), 200






# def wrap_for_mutation(obj):
#     """Return a wrapped object that will auto-convert future mutations:
#        - dict -> StrDict
#        - list/tuple -> StrList (tuples become tuple of wrapped values)
#        - uuid.UUID -> str
#        - otherwise -> as-is
#     """
#     if isinstance(obj, UUID):
#         return str(obj)
#     if isinstance(obj, StrDict) or isinstance(obj, StrList):
#         return obj
#     if isinstance(obj, Mapping):
#         return StrDict(obj)
#     if isinstance(obj, list):
#         return StrList(obj)
#     if isinstance(obj, tuple):
#         return tuple(wrap_for_mutation(x) for x in obj)
#     if isinstance(obj, (str, bytes)):
#         return obj
#     return obj


# class StrDict(dict):
#     def __init__(self, mapping=None, **kwargs):
#         mapping = mapping or {}
#         super().__init__()

#         for k, v in dict(mapping, **kwargs).items():
#             self[k] = v

#     def __setitem__(self, key, value):
#         if isinstance(key, UUID):
#             key = str(key)
#         super().__setitem__(key, wrap_for_mutation(value))

#     def update(self, mapping=(), **kwargs):
#         for k, v in dict(mapping, **kwargs).items():
#             self[k] = v

#     def setdefault(self, key, default=None):
#         if key in self:
#             return self[key]
#         self[key] = default
#         return self[key]


# class StrList(list):
#     def __init__(self, iterable=()):
#         super().__init__(wrap_for_mutation(x) for x in iterable)

#     def append(self, value):
#         super().append(wrap_for_mutation(value))

#     def extend(self, iterable):
#         super().extend(wrap_for_mutation(x) for x in iterable)

#     def insert(self, index, value):
#         super().insert(index, wrap_for_mutation(value))

#     def __setitem__(self, index, value):
#         if isinstance(index, slice):
#             wrapped = [wrap_for_mutation(x) for x in value]
#             super().__setitem__(index, wrapped)
#         else:
#             super().__setitem__(index, wrap_for_mutation(value))

#     def __iadd__(self, other):
#         self.extend(other)
#         return self


# @dataclass
# class CopyPasteRow:
#     performed_by: UUID

#     targets_were_new_employees: bool = False
#     targets_were_new_events: bool = False

#     id: UUID | None = None

#     target_event_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})
#     target_booth_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})

#     data_to_copy: dict[str, Any] = field(default_factory=dict, metadata={'convert_uuids': True})

#     event_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})
#     booth_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})
#     product_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})
#     category_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})
#     employee_ids: list[UUID | str] = field(default_factory=list, metadata={'convert_uuids': True})

#     employee_event_booth_roles_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
#     product_booth_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
#     category_booth_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
#     category_product_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})

#     occurred_at: datetime | None = None


#     def __post_init__(self):
#         for f in fields(self):
#             if f.metadata.get('convert_uuids'):
#                 original = getattr(self, f.name)
#                 wrapped = wrap_for_mutation(original)
#                 setattr(self, f.name, wrapped)

#         with open('prints.txt', 'a', encoding='utf-8') as f:
#             from pprint import pprint
#             pprint(self.employee_event_booth_roles_rows, stream=f)
#             print(self.employee_event_booth_roles_rows, file=f)


#     def to_params(self):
#         return {
#             'performed_by': self.performed_by,

#             'targets_were_new_employees': self.targets_were_new_employees,
#             'targets_were_new_events': self.targets_were_new_events,

#             'target_event_ids': Jsonb(self.target_event_ids),
#             'target_booth_ids': Jsonb(self.target_booth_ids),

#             'data_to_copy': Jsonb(self.data_to_copy),

#             'event_ids': Jsonb(self.event_ids),
#             'booth_ids': Jsonb(self.booth_ids),
#             'product_ids': Jsonb(self.product_ids),
#             'category_ids': Jsonb(self.category_ids),
#             'employee_ids': Jsonb(self.employee_ids),

#             'employee_event_booth_roles_rows': Jsonb(self.employee_event_booth_roles_rows),
#             'product_booth_link_rows': Jsonb(self.product_booth_link_rows),
#             'category_booth_link_rows': Jsonb(self.category_booth_link_rows),
#             'category_product_link_rows': Jsonb(self.category_product_link_rows)
#         }