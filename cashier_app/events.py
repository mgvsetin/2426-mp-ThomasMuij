from datetime import timezone
from dateutil import parser
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
from psycopg import IntegrityError
from argon2 import PasswordHasher
from cashier_app.employee_events_booths import load_selected_event
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_name
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

    if not employee['is_admin'] and not (employee['id'], event_id):
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

    ok, errors = validate_event_name(name)
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
# make html, css and js for my event_manager page. It should contain the event id (mute), name, start and end dates/times, created by (muted) and created at (muted) 
# It should contain a table of employees linked to that event (either managers (not linked to a booth) or ones linked to a booth (they can be linked to more booths). It should also contain a table of products, their prices and linked booths. then also a table of all the booths of that event. I will give you html, css and js of my events_manager so that you can make it in a similar style. I will also give you the sql.  
# There should be a button to edit the event (make an overlay similar to the add event overlay in my events_manager page) which allows you to edit the events table. I will give you the backend too (however , it does not yet provide capability to edit other tables linked to an event)

# events.py
    cols_str = ', '.join(params.keys())
    col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f'''
                    INSERT INTO events
                    ({cols_str})
                    VALUES ({col_values_placeholders})''',
                    (params))
    except IntegrityError as e:
        with open(r'C:\Users\thomas.muijsenberg\Documents\code\2426-mp-ThomasMuij\prints.txt', 'a', encoding='utf-8') as f:
            print(str(e), file=f)

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

    if name:
        ok, errors = validate_event_name(name)
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
    
    if end_at:
        try:
            end_at_dt = parser.isoparse(end_at)
            end_at_utc = end_at_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return jsonify(error='invalid_end_at'), 400
        
        # if end_at_utc < datetime.now():
        #     return jsonify(error='invalid_end_at_date'), 400

        params['end_at'] = end_at_utc
    
    if start_at_utc and end_at_utc:
        if start_at_utc > end_at_utc:
            return jsonify(error='invalid_start_at_end_at_dates'), 400

    if not params:
        return jsonify(error='no_column_to_update'), 400

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
                    WHERE id = %(id)s)
                    AND deleted_at IS NULL''',
                    params)
                rows_affected = cur.rowcount
                if rows_affected > 1:
                    raise RuntimeError(f'multiple rows updated for id {event_id}')
    except IntegrityError as e: # can be start_at <= end_at now, do through detail? (add detail check to others?)
        # with open(r'C:\Users\thoma\Documents\code\2426-mp-ThomasMuij\prints.txt', 'a', encoding='utf-8') as f:
        #     print(e, file=f)
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

    return jsonify(), 200