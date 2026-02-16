"""Modul pro správu událostí a stánků přihlášeného zaměstnance.

Poskytuje API endpointy pro výběr aktivní události a stánku v rámci session.
Definuje dva Flask blueprinty: 'employee_events_api' pro události
a 'booths' (vnořený pod '/booths') pro stánky.
"""

# import functools
from uuid import UUID
from flask import Blueprint, request, session, g, jsonify, url_for
from cashier_app.db import get_pool
from cashier_app.auth import load_logged_in_employee
from cashier_app.utils.employees_users import is_manager

api_bp = Blueprint('employee_events_api', __name__, url_prefix='/api/employees/me/events')


@api_bp.route('/active')
def get_active_events_for_employee():
    """Získá seznam aktivních událostí pro přihlášeného zaměstnance.

    Pokud je zaměstnanec administrátor, vrátí všechny právě probíhající události.
    V opačném případě vrátí pouze události, ke kterým je zaměstnanec přiřazen
    prostřednictvím tabulky employee_event_booth_roles.

    Returns:
        tuple: JSON seznam událostí (id, name) s kódem 200,
               nebo přesměrování na přihlášení s kódem 401.
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
                    AND start_at <= now()
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
                    AND events.start_at <= now()
                    AND (events.end_at IS NULL OR events.end_at > now())
                    AND events.deleted_at IS NULL
                    AND link.employee_id = %s
                    GROUP BY events.id
                    ORDER BY name''',
                    (employee['id'],)).fetchall()
            
    return jsonify(events), 200


@api_bp.route('/select', methods=('PUT',))
def select_event():
    """Nastaví vybranou událost do session přihlášeného zaměstnance.

    Validuje event_id z formuláře, ověřuje, zda je událost aktivní
    a zda má zaměstnanec oprávnění k dané události (admin má přístup vždy).
    Při úspěšném výběru odstraní případně zvolený stánek ze session.

    Returns:
        tuple: Prázdný JSON s kódem 200 při úspěchu,
               nebo chybová zpráva s odpovídajícím HTTP kódem (400, 401, 403, 404).
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event_id_raw = request.form.get('event')
    if not event_id_raw:
        return jsonify(error='missing_event_id'), 400
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
            
            if not event:
                return jsonify(error='event_not_found_or_inactive'), 404
    
            # ověření, zda je zaměstnanec přiřazen k události
            if not employee['is_admin']:
                role = cur.execute(
                    '''
                    SELECT role
                    FROM employee_event_booth_roles
                    WHERE employee_id = %s
                    AND event_id = %s''',
                    (employee['id'], event_id)).fetchall()
        
                if not role:
                    return jsonify(error='employee_not_linked_to_event'), 403

    session.pop('booth_id', None)
    session['event_id'] = str(event_id)
    return jsonify(), 200
        


@api_bp.route('/remove', methods=('DELETE',))
def remove_event():
    """Odstraní vybranou událost a stánek ze session.

    Slouží k zrušení aktuálního výběru události, například při přechodu
    na jinou událost. Společně s událostí se odstraní i vybraný stánek.

    Returns:
        tuple: Prázdný JSON s kódem 200.
    """
    session.pop('event_id', None)
    session.pop('booth_id', None)
    return jsonify(), 200
        

def load_selected_event() -> dict | None:
    """Načte vybranou událost ze session a uloží ji do kontextu požadavku ``g``.

    Pokud v session není nastaveno event_id, nastaví ``g.event`` na None.
    Pokud už je událost v ``g`` načtená a odpovídá session, vrátí ji přímo.
    Jinak dotáže databázi na aktivní událost s daným ID.

    Returns:
        dict | None: Slovník s údaji o události (id, name, start_at, end_at),
                     nebo None pokud žádná událost není vybrána či není aktivní.
    """
    event_id = session.get('event_id')

    if event_id is None:
        g.event = None
        return g.event
    
    if g.get('event') and g.event['id'] == event_id:
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
api_bp.register_blueprint(api_booths_bp)


@api_booths_bp.route('/active')
def get_event_booths_for_employee():
    """Získá seznam stánků vybrané události, které může zaměstnanec obsluhovat.

    Administrátor nebo správce události (event_manager) vidí všechny stánky
    dané události. Běžný zaměstnanec vidí pouze stánky, ke kterým je
    explicitně přiřazen v tabulce employee_event_booth_roles.

    Returns:
        tuple: JSON seznam stánků (id, name) s kódem 200,
               nebo chybová zpráva s kódem 400 či 401.
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
    """Nastaví vybraný stánek do session přihlášeného zaměstnance.

    Validuje booth_id z formuláře a ověřuje, zda stánek patří k vybrané události.
    Kontroluje oprávnění zaměstnance: administrátor má přístup vždy,
    správce události (event_manager) ke všem stánkům události,
    ostatní zaměstnanci pouze ke stánkům, ke kterým jsou explicitně přiřazeni.

    Returns:
        tuple: JSON s booth_type a kódem 200 při úspěchu,
               nebo chybová zpráva s odpovídajícím HTTP kódem (400, 401, 404).
    """
    employee = load_logged_in_employee()

    if employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    event = load_selected_event()

    if event is None:
        return jsonify(error='no_selected_event'), 400

    booth_id_raw = request.form.get('booth')

    if not booth_id_raw:
        return jsonify(error='missing_booth_id'), 400

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

            # ověření, zda je zaměstnanec přiřazen ke stánku
            if not employee['is_admin']:
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



@api_booths_bp.route('/remove', methods=('DELETE',))
def remove_booth():
    """Odstraní vybraný stánek ze session.

    Zruší aktuální výběr stánku, aniž by ovlivnil vybranou událost.

    Returns:
        tuple: Prázdný JSON s kódem 200.
    """
    session.pop('booth_id', None)
    return jsonify(), 200



def load_selected_booth():
    """Načte vybraný stánek ze session a uloží ho do kontextu požadavku ``g``.

    Nejprve načte vybranou událost. Pokud v session chybí booth_id nebo
    není vybrána žádná událost, nastaví ``g.booth`` na None.
    Jinak dotáže databázi na stánek s daným ID v rámci vybrané události.

    Returns:
        dict | None: Slovník s údaji o stánku (id, name, event_id, booth_type),
                     nebo None pokud žádný stánek není vybrán či neexistuje.
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
