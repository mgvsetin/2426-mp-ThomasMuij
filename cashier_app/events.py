from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_db
from cashier_app.utils.employees import is_manager, validate_username, validate_email, validate_password

bp = Blueprint('events', __name__, url_prefix='/api/events')


@bp.route('/')
def get_events_to_manage():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401
    
    conn = get_db()

    if employee['is_admin']:
        with conn.transaction():
            with conn.cursor() as cur:
                events = cur.execute('''
                    SELECT id, name, start_at, end_at, created_at
                    FROM events
                    WHERE deleted_at IS NULL
                    ORDER BY created_at''').fetchall()
    else:
        with conn.transaction():
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


@bp.route('/<uuid:event_id>')
def get_event(event_id):
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401
    
    conn = get_db()

    if not employee['is_admin'] and not is_manager(employee['id'], event_id):
        return jsonify(error='insufficient_priviliges'), 403

    with conn.transaction():
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
                    COALESCE(json_agg(
                        DISTINCT jsonb_build_object('booth_id', link.booth_id, 'role', link.role)
                        ) FILTER (WHERE link.employee_id IS NOT NULL),
                        '[]'
                    ) AS booths
                FROM employees as em
                JOIN employee_event_booth_roles AS link ON link.employee_id = em.id
                WHERE em.deleted_at IS NULL
                GROUP BY em.id
                ORDER BY em.created_at''', # WHERE link.event_id = %s
                ).fetchall()
            
            products = cur.execute('''
                SELECT p.id, p.name, p.categories, ev_link.price,
                    COALESCE(json_agg(
                        DISTINCT jsonb_build_object('booth_id', bo_link.booth_id)
                        ),
                        '[]'
                    ) AS booths
                FROM products as p
                JOIN product_event_prices AS ev_link ON ev_link.product_id = p.id
                JOIN event_product_booth_link AS bo_link ON bo_link.product_event_prices_id = ev_link.id
                WHERE ev_link.event_id = %s
                GROUP BY ev_link.id, p.id
                ORDER BY ev_link.created_at''',
                (event_id,)).fetchall()
            
            booths = cur.execute('''
                SELECT id, name, booth_type
                FROM booths
                WHERE event_id = %s
                AND deleted_at IS NULL''',
                (event_id,)).fetchall()
            
    return jsonify(event=event, employees=employees, products=products, booths=booths), 200


@bp.route('/create', methods=('POST',))
def add_employee(): 
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    if not logged_employee['is_admin']:
        return jsonify(error='insufficient_priviliges'), 403

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password_raw = request.form.get('password', '')

    if not username:
        return jsonify(error='missing_username'), 400
    
    if not email:
        return jsonify(error='missing_email'), 400
    
    if not password_raw:
        return jsonify(error='missing_password'), 400


    ok, errors = validate_username(username)
    if not ok:
        return jsonify(error=errors[0]), 400

    ok, errors = validate_email(email)
    if not ok:
        return jsonify(error="invalid_email"), 400    

    ok, errors = validate_password(password_raw)
    if not ok:
        return jsonify(error=errors[0]), 400
    
    password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
    password_hash = password_hasher.hash(password_raw)        

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO employees
                    (username, email, password_hash, created_by)
                    VALUES (%s, %s, %s, %s)''',
                    (username, email, password_hash, logged_employee['id']))

    except IntegrityError as e:
        return jsonify(error='db_integrity_error', detail=str(e)), 400

    return jsonify(), 200


@bp.route('/edit', methods=('POST',))
def edit_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    try:
        edit_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not edit_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != edit_employee_id:
        return jsonify(error='insufficient_priviliges'), 403

    new_username = request.form.get('username', '').strip()
    new_email = request.form.get('email', '').strip().lower()
    new_password_raw = request.form.get('password', '')

    col_updates = []
    params = {'edit_employee_id': edit_employee_id}

    if new_username:
        ok, errors = validate_username(new_username)
        if not ok:
            return jsonify(error=errors[0]), 400
        col_updates.append('username = %(new_username)s')
        params['new_username'] = new_username
    
    if new_email:
        ok, errors = validate_email(new_email)
        if not ok:
            return jsonify(error="invalid_email"), 400
        col_updates.append('email = %(new_email)s')
        params['new_email'] = new_email
        
    if new_password_raw:
        ok, errors = validate_password(new_password_raw)
        if not ok:
            return jsonify(error=errors[0]), 400
        
        password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
        new_password_hash = password_hasher.hash(new_password_raw)

        col_updates.append('password_hash = %(new_password_hash)s')
        params['new_password_hash'] = new_password_hash

        

    if not col_updates:
        return jsonify(error='no_column_updated'), 400

    col_updates_str = ', '.join(col_updates)

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(f'''
                    UPDATE employees
                    SET {col_updates_str}
                    WHERE id = %(edit_employee_id)s
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {edit_employee_id}')
    except IntegrityError as e:
        return jsonify(error='db_integrity_error', detail=str(e)), 400
    except RuntimeError:
        current_app.logger.exception('multiple rows updated for employee id %s', edit_employee_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='employee_not_found'), 404

    return jsonify(), 200


@bp.route('/delete', methods=('DELETE',))
def delete_employee():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    try:
        delete_employee_id = UUID(request.form.get('id'))
    except ValueError:
        return jsonify(error='invalid_id'), 400

    if not delete_employee_id:
        return jsonify(error='missing_id'), 400

    if not logged_employee['is_admin'] and logged_employee['id'] != delete_employee_id:
        return jsonify(error='insufficient_priviliges'), 403

    conn = get_db()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE employees
                    SET deleted_at = now()
                    WHERE id = %s
                    AND deleted_at IS NULL''',
                    (delete_employee_id,))
                
                rows_affected = cur.rowcount

                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows deleted for id {delete_employee_id}')
    except RuntimeError:
        current_app.logger.exception('multiple rows deleted for employee id %s', delete_employee_id)
        return jsonify(error='internal_server_error'), 500


    if rows_affected == 0:
        return jsonify(error='employee_not_found'), 404

    return jsonify(), 200