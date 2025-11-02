# import functools
from uuid import UUID
from flask import Blueprint, request, session, g, jsonify, make_response, url_for
from cashier_app.db import get_db
from cashier_app.auth import load_logged_in_employee

bp = Blueprint('events', __name__, url_prefix='/api/employees/me/events')


@bp.route('/active')
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
                    AND link.employee_id = %s
                    GROUP BY events.id''',
                    (employee['id'],)).fetchall()
            
    return jsonify(events), 200


@bp.route('/select', methods=('PUT',))
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
    
    # ověř zda zaměstanec je spojený s akcí
    if not employee['is_admin']:
        with conn.transaction():
            with conn.cursor() as cur:
                role = cur.execute('''
                    SELECT role
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s''',
                    (employee['id'], event_id)).fetchall()
        
        if not role:
            return jsonify(error='employee_not_linked_to_event'), 403

    if event:
        session.pop('booth_id', None)
        session['event_id'] = str(event_id)
        return jsonify(), 200
    else:
        return jsonify(error='event_not_found_or_inactive'), 404


@bp.route('/remove', methods=('DELETE',))
def remove_event():
    session.pop('event_id', None)
    session.pop('booth_id', None)
    return jsonify(), 200
        

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


@bp_booths.route('/active')
def get_event_booths_for_employee():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    event = load_selected_event()

    if event is None:
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
                    (event['id'],)).fetchall()
            else:
                is_manager = cur.execute('''
                    SELECT 1
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s
                    AND role = 'event_manager' ''',
                    (employee['id'], event['id'])).fetchone()
                
                if is_manager:
                    booths = cur.execute(all_event_booths_sql,
                    (event['id'],)).fetchall()
                else:
                    booths = cur.execute('''
                        SELECT booths.id, booths.name
                        FROM booths
                        JOIN employee_event_booth_roles AS roles ON roles.booth_id = booths.id
                        WHERE booths.event_id = %s
                        AND booths.deleted_at IS NULL
                        AND roles.employee_id = %s''',
                        (event['id'], employee['id'])).fetchall()
    return jsonify(booths), 200


@bp_booths.route('/select', methods=('PUT',))
def select_booth():
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    event = load_selected_event()

    if event is None:
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
                (booth_id, event['id'])).fetchone()
            
    if booth is None:
        return jsonify(error='booth_not_found'), 404

    # ověř zda je zaměstanenc spojený se stánkem:
    if not employee['is_admin']:
        with conn.transaction():
            with conn.cursor() as cur:
                event_link = cur.execute('''
                    SELECT role
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s''',
                    (employee['id'], event['id'])).fetchall()
                
                if not event_link:
                    return jsonify(error='employee_not_linked_to_event'), 400
                
                if event_link[0]['role'] != 'event_manager':
                    booth_link = cur.execute('''
                        SELECT role
                        FROM employee_event_booth_roles
                        WHERE employee_id = %s
                        AND event_id = %s
                        AND booth_id = %s''',
                        (employee['id'], event['id'], booth_id)).fetchone()
                    
                    if not booth_link:
                        return jsonify(error='employee_not_linked_to_booth'), 400

    is_allowed = not booth['auth_required']
    
    if not is_allowed:
        is_allowed = employee['is_admin']

    if not is_allowed:  
        if event_link[0]['role'] == 'event_manager':
            is_allowed = True

    # if not is_allowed:
    #     auth_username_or_email = request.form.get('username-email')
    #     auth_password = request.form.get('password')
    #     # split the authentication from the login func and use here

    if not is_allowed:
        return jsonify(error='employee_does_not_have_permission_for_booth'), 403
    
    session['booth_id'] = str(booth_id)
    return jsonify(), 200



def load_selected_booth():
    booth_id = session.get('booth_id')
    event = load_selected_event()

    if booth_id is None or event is None:
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
                (booth_id, event['id'])).fetchone()

    return g.booth


@bp_booths.route('/products')
def get_products():
    employee = load_logged_in_employee()
    event = load_selected_event()
    booth = load_selected_booth()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.login')), 401

    if event is None:
        return jsonify(error='no_selected_event'), 400

    if booth is None:
        return jsonify(error='no_selected_booth'), 400
    
    conn = get_db()
    
    with conn.transaction():
        with conn.cursor() as cur:
            products = cur.execute('''
                SELECT products.id, products.name, price.price, images.image_path, images.filename
                FROM event_product_booth_link as link
                JOIN product_event_prices as price ON link.product_event_prices_id = price.id
                JOIN products ON products.id = price.product_id
                LEFT JOIN product_images AS images ON images.product_id = products.id
                WHERE link.booth_id = %s''', # group by products.id
                (booth['id'],)).fetchall()
    
    return jsonify(products), 200


bp.register_blueprint(bp_booths)