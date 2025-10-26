# import functools
from uuid import UUID
from flask import Blueprint, request, session, g, jsonify, make_response, url_for
from cashier_app.db import get_db
from cashier_app.auth import load_logged_in_employee

bp = Blueprint('events', __name__, url_prefix='/events')


@bp.route('/get-active-for-employee')
def get_active_events_for_employee():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    conn = get_db()

    with conn.transaction():
        with conn.cursor() as cur:
            if employee['is_admin']:
                events = cur.execute('''
                    SELECT id, name
                    FROM events
                    WHERE start_at IS NOT NULL
                    AND start_at < now()
                    AND (end_at IS NULL OR end_at > now())
                    AND deleted_at IS NULL'''
                    ).fetchall()
            else:
                events = cur.execute('''
                    SELECT events.id, events.name
                    FROM events
                    JOIN employee_event_booth_roles AS link ON link.event_id = events.id
                    WHERE events.start_at IS NOT NULL
                    AND events.start_at < now()
                    AND (events.end_at IS NULL OR events.end_at > now())
                    AND events.deleted_at IS NULL
                    AND link.employee_id = %s''',
                    (employee['id'],)).fetchall()
            
    return jsonify(events), 200


@bp.route('/select', methods=('POST',))
def select_event():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    event_id_raw = request.form.get('event')
    try:
        event_id = str(UUID(event_id_raw))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    conn = get_db()
    with conn.transaction():
        with conn.cursor() as cur:
            event = cur.execute('''
                SELECT id
                FROM events
                WHERE id = %s
                AND start_at IS NOT NULL
                AND start_at < now()
                AND (end_at IS NULL OR end_at > now())
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()
    
    if not employee['is_admin']:
        with conn.transaction():
            with conn.cursor() as cur:
                role = cur.execute('''
                    SELECT role
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s''',
                    (employee['id'], event_id)).fetchone()
                
        if role is None:
            return jsonify(error='employee_not_linked_to_event'), 403

    if event:
        session['event_id'] = str(event_id)
        return jsonify(), 200
    else:
        return jsonify(error='event_not_found_or_inactive'), 404
        

def load_selected_event() -> dict | None:
    event_id = session.get('event_id')

    if event_id is None:
        g.event = None
        return g.event
    
    conn = get_db()
    with conn.transaction():
        with conn.cursor() as cur:
            g.event = cur.execute('''
                SELECT id, name, start_at, end_at
                FROM events
                WHERE id = %s
                AND start_at IS NOT NULL
                AND start_at < now()
                AND (end_at IS NULL OR end_at > now())
                AND deleted_at IS NULL''',
                (event_id,)).fetchone()

    return g.event


# def event_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         load_selected_event()
#         if g.event is None:
#             jsonify(success=False, error='event_required', redirect_url=url_for('order.index')), 401
        
#         return view(**kwargs)
    
#     return wrapped_view



bp_booths = Blueprint('booths', __name__, url_prefix='/booths')


@bp_booths.route('/get-for-employee')
def get_event_booths_for_employee():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    event_id = session.get('event_id')

    if event_id is None:
        return jsonify(error='no_selected_event'), 400

    conn = get_db()

    all_event_booths_sql = '''
                    SELECT id, name
                    FROM booths
                    WHERE event_id = %s
                    AND deleted_at IS NULL'''

    with conn.transaction():
        with conn.cursor() as cur:
            # is_event_manager = 

            if employee['is_admin']:
                booths = cur.execute(all_event_booths_sql,
                    (event_id,)).fetchall()
            else:
                is_manager = cur.execute('''
                    SELECT 1
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s
                    AND role = "event_manager" ''',
                    (employee['id', event_id])).fetchone()
                
                if is_manager:
                    booths = cur.execute(all_event_booths_sql,
                    (event_id,)).fetchall()
                else:
                    booths = cur.execute('''
                        SELECT booths.id, booths.name
                        FROM booths
                        JOIN employee_event_booth_roles AS roles ON roles.booth_id = booths.id
                        WHERE booths.event_id = %s
                        AND booths.deleted_at IS NULL
                        AND roles.employee_id = %s''',
                        (event_id, employee['id'])).fetchall()
    return jsonify(booths), 200


@bp_booths.route('/select', methods=('POST',))
def select_booth():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    event_id = session.get('event_id')

    if event_id is None:
        return jsonify(error='no_selected_event'), 400

    booth_id_raw = request.form.get('booth')

    try:
        booth_id = str(UUID(booth_id_raw))
    except (TypeError, ValueError):
        return jsonify(error='invalid_booth_id'), 400

    conn = get_db()

    with conn.transaction():
        with conn.cursor() as cur:
            booth = cur.execute('''
                SELECT booth_type, auth_required
                FROM booths
                WHERE id = %s
                AND event_id = %s
                AND deleted_at IS NULL''',
                (booth_id, event_id)).fetchone()
            
    if booth is None:
        return jsonify(error='booth_not_found'), 404
            
    is_allowed = not booth['auth_required']
    
    if not is_allowed:
        is_allowed = employee['is_admin']

    if not is_allowed:
        with conn.transaction():
            with conn.cursor() as cur:
                    role = cur.execute('''
                        SELECT role
                        FROM employee_event_booth_roles
                        WHERE employee_id = %s
                        AND event_id = %s
                        AND booth_id IS NULL''',
                        (employee['id'], event_id)).fetchone()
                    
                    if role is None:
                        return jsonify(error='employee_not_linked_to_event'), 403
                    
                    if role['role'] == 'event_manager': # stejné jako if role:
                        is_allowed = True

    # if not is_allowed:
    #     auth_username_or_email = request.form.get('username-email')
    #     auth_password = request.form.get('password')
    #     # split the authentication from the login func and use here

    if not is_allowed:
        return jsonify(error='event_not_found_or_inactive'), 404
    
    session['booth_id'] = str(booth_id)
    return jsonify(), 200



def load_selected_booth():
    booth_id = session.get('booth_id')
    event_id = session.get('event_id')

    if booth_id is None:
        g.booth = None
        return g.booth
    
    conn = get_db()
    
    with conn.transaction():
        with conn.cursor() as cur:
            g.booth = cur.execute('''
                SELECT id, name, event_id, booth_type
                FROM booths
                WHERE id = %s
                AND event_id = %s
                AND deleted_at IS NULL''',
                (booth_id, event_id)).fetchone()

    return g.booth



bp.register_blueprint(bp_booths)