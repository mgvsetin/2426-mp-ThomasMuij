"""Funkce pro synchronizaci vazebních tabulek v systému undo/redo.

Tyto funkce synchronizují vazební tabulky (DELETE all + INSERT new) a vrací
záznamy o změnách (diff – co bylo přidáno/odebráno).
"""

from psycopg import Cursor

from cashier_app.utils.cascade_capture import convert_dict_to_serializable
from cashier_app.utils.query_builder import build_insert_statement


def sync_product_booth_links(cur: Cursor, product_id, new_booth_ids: list) -> list[dict]:
    """Synchronizuje vazby product_booth_link pro produkt.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_booth_ids = new_booth_ids or []
    new_booth_ids_set = {str(bid) for bid in new_booth_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT product_id, booth_id FROM product_booth_link WHERE product_id = %s',
        (product_id,)
    ).fetchall()
    old_booth_ids_set = {str(link['booth_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM product_booth_link WHERE product_id = %s', (product_id,))

    # 3. Vložení nových vazeb
    if new_booth_ids:
        rows = [{'product_id': product_id, 'booth_id': booth_id}
                for booth_id in new_booth_ids]
        sql, query_params = build_insert_statement('product_booth_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    # Vazby, které byly odebrány
    for link in old_links:
        if str(link['booth_id']) not in new_booth_ids_set:
            changes.append({
                'table': 'product_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    # Vazby, které byly přidány
    for booth_id in new_booth_ids:
        if str(booth_id) not in old_booth_ids_set:
            changes.append({
                'table': 'product_booth_link',
                'old_values': None,
                'new_values': {'product_id': str(product_id), 'booth_id': str(booth_id)}
            })

    return changes


def sync_booth_product_links(cur: Cursor, booth_id, new_product_ids: list) -> list[dict]:
    """Synchronizuje vazby product_booth_link pro stánek.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_product_ids = new_product_ids or []
    new_product_ids_set = {str(pid) for pid in new_product_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT product_id, booth_id FROM product_booth_link WHERE booth_id = %s',
        (booth_id,)
    ).fetchall()
    old_product_ids_set = {str(link['product_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM product_booth_link WHERE booth_id = %s', (booth_id,))

    # 3. Vložení nových vazeb
    if new_product_ids:
        rows = [{'product_id': product_id, 'booth_id': booth_id}
                for product_id in new_product_ids]
        sql, query_params = build_insert_statement('product_booth_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for link in old_links:
        if str(link['product_id']) not in new_product_ids_set:
            changes.append({
                'table': 'product_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    for product_id in new_product_ids:
        if str(product_id) not in old_product_ids_set:
            changes.append({
                'table': 'product_booth_link',
                'old_values': None,
                'new_values': {'product_id': str(product_id), 'booth_id': str(booth_id)}
            })

    return changes


def sync_category_booth_links(cur: Cursor, category_id, new_booth_ids: list) -> list[dict]:
    """Synchronizuje vazby category_booth_link pro kategorii.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_booth_ids = new_booth_ids or []
    new_booth_ids_set = {str(bid) for bid in new_booth_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT category_id, booth_id FROM category_booth_link WHERE category_id = %s',
        (category_id,)
    ).fetchall()
    old_booth_ids_set = {str(link['booth_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM category_booth_link WHERE category_id = %s', (category_id,))

    # 3. Vložení nových vazeb
    if new_booth_ids:
        rows = [{'category_id': category_id, 'booth_id': booth_id}
                for booth_id in new_booth_ids]
        sql, query_params = build_insert_statement('category_booth_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for link in old_links:
        if str(link['booth_id']) not in new_booth_ids_set:
            changes.append({
                'table': 'category_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    for booth_id in new_booth_ids:
        if str(booth_id) not in old_booth_ids_set:
            changes.append({
                'table': 'category_booth_link',
                'old_values': None,
                'new_values': {'category_id': str(category_id), 'booth_id': str(booth_id)}
            })

    return changes


def sync_booth_category_links(cur: Cursor, booth_id, new_category_ids: list) -> list[dict]:
    """Synchronizuje vazby category_booth_link pro stánek.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_category_ids = new_category_ids or []
    new_category_ids_set = {str(cid) for cid in new_category_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT category_id, booth_id FROM category_booth_link WHERE booth_id = %s',
        (booth_id,)
    ).fetchall()
    old_category_ids_set = {str(link['category_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM category_booth_link WHERE booth_id = %s', (booth_id,))

    # 3. Vložení nových vazeb
    if new_category_ids:
        rows = [{'category_id': category_id, 'booth_id': booth_id}
                for category_id in new_category_ids]
        sql, query_params = build_insert_statement('category_booth_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for link in old_links:
        if str(link['category_id']) not in new_category_ids_set:
            changes.append({
                'table': 'category_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    for category_id in new_category_ids:
        if str(category_id) not in old_category_ids_set:
            changes.append({
                'table': 'category_booth_link',
                'old_values': None,
                'new_values': {'category_id': str(category_id), 'booth_id': str(booth_id)}
            })

    return changes


def sync_category_product_links(cur: Cursor, category_id, new_product_ids: list) -> list[dict]:
    """Synchronizuje vazby category_product_link pro kategorii.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_product_ids = new_product_ids or []
    new_product_ids_set = {str(pid) for pid in new_product_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT category_id, product_id FROM category_product_link WHERE category_id = %s',
        (category_id,)
    ).fetchall()
    old_product_ids_set = {str(link['product_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM category_product_link WHERE category_id = %s', (category_id,))

    # 3. Vložení nových vazeb
    if new_product_ids:
        rows = [{'category_id': category_id, 'product_id': product_id}
                for product_id in new_product_ids]
        sql, query_params = build_insert_statement('category_product_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for link in old_links:
        if str(link['product_id']) not in new_product_ids_set:
            changes.append({
                'table': 'category_product_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    for product_id in new_product_ids:
        if str(product_id) not in old_product_ids_set:
            changes.append({
                'table': 'category_product_link',
                'old_values': None,
                'new_values': {'category_id': str(category_id), 'product_id': str(product_id)}
            })

    return changes


def sync_product_category_links(cur: Cursor, product_id, new_category_ids: list) -> list[dict]:
    """Synchronizuje vazby category_product_link pro produkt.

    Smaže všechny existující vazby a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).
    """
    changes = []
    new_category_ids = new_category_ids or []
    new_category_ids_set = {str(cid) for cid in new_category_ids}

    # 1. Dotaz na aktuální vazby
    old_links = cur.execute(
        'SELECT category_id, product_id FROM category_product_link WHERE product_id = %s',
        (product_id,)
    ).fetchall()
    old_category_ids_set = {str(link['category_id']) for link in old_links}

    # 2. Smazání všech existujících
    cur.execute('DELETE FROM category_product_link WHERE product_id = %s', (product_id,))

    # 3. Vložení nových vazeb
    if new_category_ids:
        rows = [{'category_id': category_id, 'product_id': product_id}
                for category_id in new_category_ids]
        sql, query_params = build_insert_statement('category_product_link', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for link in old_links:
        if str(link['category_id']) not in new_category_ids_set:
            changes.append({
                'table': 'category_product_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    for category_id in new_category_ids:
        if str(category_id) not in old_category_ids_set:
            changes.append({
                'table': 'category_product_link',
                'old_values': None,
                'new_values': {'category_id': str(category_id), 'product_id': str(product_id)}
            })

    return changes


def sync_employee_event_booth_roles(cur: Cursor, employee_id, event_id, new_booth_ids: list) -> list[dict]:
    """Synchronizuje role zaměstnance (employee_event_booth_roles) v rámci události.

    Smaže všechny existující role pro daného zaměstnance a událost a vloží nové.
    Vrátí seznam změnových záznamů pro sledování undo (pouze diff).

    Poznámka: booth_id může být NULL pro roli manažera události.
    """
    changes = []
    new_booth_ids = new_booth_ids or []
    # Převod na řetězce, None pro roli manažera události
    new_booth_ids_set = {str(bid) if bid is not None else None for bid in new_booth_ids}

    # 1. Dotaz na aktuální role
    old_roles = cur.execute(
        '''SELECT employee_id, event_id, booth_id, role
           FROM employee_event_booth_roles
           WHERE employee_id = %s AND event_id = %s''',
        (employee_id, event_id)
    ).fetchall()
    old_booth_ids_set = {str(role['booth_id']) if role['booth_id'] is not None else None for role in old_roles}

    # 2. Smazání všech existujících
    cur.execute(
        'DELETE FROM employee_event_booth_roles WHERE employee_id = %s AND event_id = %s',
        (employee_id, event_id)
    )

    # 3. Vložení nových rolí
    if new_booth_ids:
        rows = [{'employee_id': employee_id, 'event_id': event_id, 'booth_id': booth_id}
                for booth_id in new_booth_ids]
        sql, query_params = build_insert_statement('employee_event_booth_roles', rows)
        cur.execute(sql, query_params)

    # 4. Sestavení změnových záznamů (pouze diff)
    for role in old_roles:
        booth_id_str = str(role['booth_id']) if role['booth_id'] is not None else None
        if booth_id_str not in new_booth_ids_set:
            changes.append({
                'table': 'employee_event_booth_roles',
                'old_values': convert_dict_to_serializable(dict(role)),
                'new_values': None
            })

    for booth_id in new_booth_ids:
        bid_str = str(booth_id) if booth_id is not None else None
        if bid_str not in old_booth_ids_set:
            changes.append({
                'table': 'employee_event_booth_roles',
                'old_values': None,
                'new_values': {
                    'employee_id': str(employee_id),
                    'event_id': str(event_id),
                    'booth_id': str(booth_id) if booth_id is not None else None
                }
            })

    return changes
