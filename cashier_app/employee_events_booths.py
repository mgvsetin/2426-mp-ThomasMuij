"""Modul pro správu akcí, stánků a výběru událostí pro zaměstnance.


Obsahuje dva blueprinty: 'events' (hlavní) a 'booths' (pod '/booths').
"""

# import functools
from uuid import UUID
from flask import Blueprint, request, session, g, jsonify, make_response, url_for
from cashier_app.db import get_pool
from cashier_app.auth import load_logged_in_employee
from cashier_app.utils.employees import is_manager
from cashier_app.utils.products import convert_image_paths_from_relative

api_bp = Blueprint('employee_events_api', __name__, url_prefix='/api/employees/me/events')


@api_bp.route('/active')
def get_active_events_for_employee():
    """Vrátí aktivní (práve probíhající) události pro přihlášeného zaměstnance.


    Pokud je zaměstnanec admin, vrátí se seznam všech aktivních akcí.
    Jinak se vrátí pouze akce, ke kterým je zaměstnanec připojen.
    
    
    Vrátí
    ------
    Response JSON
    Seznam akcí nebo error redirect na login s odpověí 401.
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401


    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if employee['is_admin']:
                events = cur.execute(
                    '''
                    SELECT id, name
                    FROM events
                    WHERE start_at IS NOT NULL
                    AND start_at < now()
                    AND (end_at IS NULL OR end_at > now())
                    AND deleted_at IS NULL
                    ORDER BY name'''
                    ).fetchall()
            else:
                events = cur.execute(
                    '''
                    SELECT events.id, events.name
                    FROM events
                    JOIN employee_event_booth_roles AS link ON link.event_id = events.id
                    WHERE events.start_at IS NOT NULL
                    AND events.start_at < now()
                    AND (events.end_at IS NULL OR events.end_at > now())
                    AND events.deleted_at IS NULL
                    AND link.employee_id = %s
                    GROUP BY events.id
                    ORDER BY name''',
                    (employee['id'],)).fetchall()
            
    return jsonify(events), 200


@api_bp.route('/select', methods=('PUT',))
def select_event():
    """Vybere událost pro aktuální session zaměstnance.


    Ošetřuje validitu event_id, kontroluje,
    zda je událost aktivní a zda je zaměstnanec s akcí svázaný (pokud není admin).
    Odstraní booth_id ze session pokud tam je.
    
    
    Vrátí
    ------
    200 prázdný JSON pokud OK, jinak chybový kód a chybová zpráva.
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event_id_raw = request.form.get('event')
    try:
        event_id = str(UUID(event_id_raw))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event = cur.execute(
                '''
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
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                role = cur.execute(
                    '''
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


@api_bp.route('/remove', methods=('DELETE',))
def remove_event():
    """Odstraní vybranou událost a stánek z aktuální session.


    Použito pro "odhlášení" vybrávání události (např. při přechodu mezi akcemi).
    """
    session.pop('event_id', None)
    session.pop('booth_id', None)
    return jsonify(), 200
        

def load_selected_event() -> dict | None:
    """Načte vybranou událost ze session a uloží ji do `g`.


    Vrátí slovník s informacemi o události nebo None pokud nic vybráno.
    """
    event_id = session.get('event_id')

    if event_id is None:
        g.event = None
        return g.event
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            g.event = cur.execute(
                '''
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



api_booths_bp = Blueprint('booths', __name__, url_prefix='/booths')


@api_booths_bp.route('/active')
def get_event_booths_for_employee():
    """Vrátí seznam stánků pro vybranou událost, které může zaměstnanec obsluhovat.


    Pokud je zaměstnanec admin nebo event_manager vrátí se všechny stánky události.
    Jinak pouze stánky, ke kterým je zaměstnanec explicitně prirazen.
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event = load_selected_event()

    if event is None:
        return jsonify(error='no_selected_event'), 400
    

    all_event_booths_sql = '''
                    SELECT id, name
                    FROM booths
                    WHERE event_id = %s
                    AND deleted_at IS NULL'''

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # is_event_manager = 

            if employee['is_admin']:
                booths = cur.execute(all_event_booths_sql,
                    (event['id'],)).fetchall()
            else:                
                if is_manager(employee['id'], event['id']):
                    booths = cur.execute(all_event_booths_sql,
                    (event['id'],)).fetchall()
                else:
                    booths = cur.execute(
                        '''
                        SELECT booths.id, booths.name
                        FROM booths
                        JOIN employee_event_booth_roles AS roles ON roles.booth_id = booths.id
                        WHERE booths.event_id = %s
                        AND booths.deleted_at IS NULL
                        AND roles.employee_id = %s
                        ORDER BY name''',
                        (event['id'], employee['id'])).fetchall()
    return jsonify(booths), 200


@api_booths_bp.route('/select', methods=('PUT',))
def select_booth():
    """Vybere stánek pro aktuální session.


    Validuje vstup, kontroluje oprávňění zaměstnance (admin, event_manager nebo explicitně
    prirazený ke stánku) a uloží booth_id do session.
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event = load_selected_event()

    if event is None:
        return jsonify(error='no_selected_event'), 400

    booth_id_raw = request.form.get('booth')

    try:
        booth_id = str(UUID(booth_id_raw))
    except (TypeError, ValueError):
        return jsonify(error='invalid_booth_id'), 400


    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            booth = cur.execute(
                '''
                SELECT booth_type
                FROM booths
                WHERE id = %s
                AND event_id = %s
                AND deleted_at IS NULL''',
                (booth_id, event['id'])).fetchone()
            
    if booth is None:
        return jsonify(error='booth_not_found'), 404

    # ověř zda je zaměstanenc spojený se stánkem:
    if not employee['is_admin']:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                event_link = cur.execute(
                    '''
                    SELECT role
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s''',
                    (employee['id'], event['id'])).fetchall()
                
                if not event_link:
                    return jsonify(error='employee_not_linked_to_event'), 400
                
                if event_link[0]['role'] != 'event_manager':
                    booth_link = cur.execute(
                        '''
                        SELECT role
                        FROM employee_event_booth_roles
                        WHERE employee_id = %s
                        AND event_id = %s
                        AND booth_id = %s''',
                        (employee['id'], event['id'], booth_id)).fetchone()
                    
                    if not booth_link:
                        return jsonify(error='employee_not_linked_to_booth'), 400
    
    session['booth_id'] = str(booth_id)
    return jsonify(booth_type=booth['booth_type']), 200



def load_selected_booth():
    """Načte vybraný stánek ze session a ulož do `g`.


    Vrátí slovník s informacemi o stánku nebo None pokud nic vybráno.
    """
    booth_id = session.get('booth_id')
    event = load_selected_event()

    if booth_id is None or event is None:
        g.booth = None
        return g.booth
    
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            g.booth = cur.execute(
                '''
                SELECT id, name, event_id, booth_type
                FROM booths
                WHERE id = %s
                AND event_id = %s
                AND deleted_at IS NULL''',
                (booth_id, event['id'])).fetchone()

    return g.booth


@api_booths_bp.route('/products+categories')
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
                SELECT p.id, p.name, p.price, p.image_path,
                  COALESCE(jsonb_agg(
                      DISTINCT jsonb_build_object('name', cat.name)
                      ) FILTER (WHERE cat_link.category_id IS NOT NULL),
                      '[]'
                  ) AS categories
                FROM products AS p
                JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                LEFT JOIN category_product_link AS cat_link ON cat_link.product_id = p.id
                LEFT JOIN categories AS cat ON cat.id = cat_link.category_id
                WHERE bo_link.booth_id = %s
                GROUP BY p.id''',
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


api_bp.register_blueprint(api_booths_bp)
