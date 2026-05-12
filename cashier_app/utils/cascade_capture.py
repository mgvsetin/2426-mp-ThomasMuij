"""Funkce pro kaskádové zachycení dat v systému undo/redo.

Tyto funkce zachytí všechna data, která budou ovlivněna operací mazání,
a umožní tak vrácení změn jako jedné atomické akce.
"""


from typing import Any, List
from psycopg import Cursor
from uuid import UUID
from datetime import datetime, date, time


def _convert(value: Any) -> Any:
    """Rekurzivně převede hodnotu na JSON-serializovatelný formát (UUID → str, datetime → ISO)."""
    if value is None:
        return None
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, (datetime, date, time)):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: _convert(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple, set)):
        return [_convert(item) for item in value]
    else:
        return value


def convert_dict_to_serializable(row: dict) -> dict:
    """Převede řádek z databáze na JSON-serializovatelný slovník s UUID jako řetězci."""
    return {k: _convert(v) for k, v in row.items()}


def capture_event_cascade(cur: Cursor, event_id) -> List[dict]:
    """Zachytí všechna data ovlivněná smazáním události.

    Vrátí seznam změnových záznamů pro sledování undo.
    Zachycuje: událost, stánky, produkty, kategorie, vazební tabulky, role zaměstnanců, peněženky.
    """
    changes = []

    # 1. Zachycení události
    event = cur.execute(
        'SELECT * FROM events WHERE id = %s AND deleted_at IS NULL',
        (event_id,)
    ).fetchone()
    if event:
        changes.append({
            'table': 'events',
            'old_values': convert_dict_to_serializable(dict(event)),
            'new_values': None
        })

    # 2. Zachycení všech stánků
    booths = cur.execute(
        'SELECT * FROM booths WHERE event_id = %s AND deleted_at IS NULL',
        (event_id,)
    ).fetchall()
    booth_ids = [b['id'] for b in booths]
    for booth in booths:
        changes.append({
            'table': 'booths',
            'old_values': convert_dict_to_serializable(dict(booth)),
            'new_values': None
        })

    # 3. Zachycení všech produktů
    products = cur.execute(
        'SELECT * FROM products WHERE event_id = %s AND deleted_at IS NULL',
        (event_id,)
    ).fetchall()
    product_ids = [p['id'] for p in products]
    for product in products:
        changes.append({
            'table': 'products',
            'old_values': convert_dict_to_serializable(dict(product)),
            'new_values': None
        })

    # 4. Zachycení všech kategorií
    categories = cur.execute(
        'SELECT * FROM categories WHERE event_id = %s AND deleted_at IS NULL',
        (event_id,)
    ).fetchall()
    category_ids = [c['id'] for c in categories]
    for category in categories:
        changes.append({
            'table': 'categories',
            'old_values': convert_dict_to_serializable(dict(category)),
            'new_values': None
        })

    # 5. Zachycení vazebních tabulek
    if booth_ids:
        product_booth_links = cur.execute(
            'SELECT * FROM product_booth_link WHERE booth_id = ANY(%s)',
            (booth_ids,)
        ).fetchall()
        for link in product_booth_links:
            changes.append({
                'table': 'product_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

        category_booth_links = cur.execute(
            'SELECT * FROM category_booth_link WHERE booth_id = ANY(%s)',
            (booth_ids,)
        ).fetchall()
        for link in category_booth_links:
            changes.append({
                'table': 'category_booth_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    if product_ids or category_ids:
        # Zachycení category_product_links odkazujících na naše produkty nebo kategorie
        category_product_links = cur.execute(
            '''SELECT * FROM category_product_link
               WHERE product_id = ANY(%s) OR category_id = ANY(%s)''',
            (product_ids if product_ids else [], category_ids if category_ids else [])
        ).fetchall()
        for link in category_product_links:
            changes.append({
                'table': 'category_product_link',
                'old_values': convert_dict_to_serializable(dict(link)),
                'new_values': None
            })

    # 6. Zachycení rolí zaměstnanců
    roles = cur.execute(
        'SELECT * FROM employee_event_booth_roles WHERE event_id = %s',
        (event_id,)
    ).fetchall()
    for role in roles:
        changes.append({
            'table': 'employee_event_booth_roles',
            'old_values': convert_dict_to_serializable(dict(role)),
            'new_values': None
        })

    # 7. Zachycení peněženek
    wallets = cur.execute(
        'SELECT * FROM wallets WHERE event_id = %s AND deleted_at IS NULL',
        (event_id,)
    ).fetchall()
    for wallet in wallets:
        changes.append({
            'table': 'wallets',
            'old_values': convert_dict_to_serializable(dict(wallet)),
            'new_values': None
        })

    return changes


def capture_booth_cascade(cur: Cursor, booth_id) -> List[dict]:
    """Zachytí všechna data ovlivněná smazáním stánku.

    Vrátí seznam změnových záznamů pro sledování undo.
    Zachycuje: stánek, vazební tabulky (product_booth_link, category_booth_link), role zaměstnanců.
    """
    changes = []

    # 1. Zachycení stánku
    booth = cur.execute(
        'SELECT * FROM booths WHERE id = %s AND deleted_at IS NULL',
        (booth_id,)
    ).fetchone()
    if booth:
        changes.append({
            'table': 'booths',
            'old_values': convert_dict_to_serializable(dict(booth)),
            'new_values': None
        })

    # 2. Zachycení vazeb produktů
    product_links = cur.execute(
        'SELECT * FROM product_booth_link WHERE booth_id = %s',
        (booth_id,)
    ).fetchall()
    for link in product_links:
        changes.append({
            'table': 'product_booth_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    # 3. Zachycení vazeb kategorií
    category_links = cur.execute(
        'SELECT * FROM category_booth_link WHERE booth_id = %s',
        (booth_id,)
    ).fetchall()
    for link in category_links:
        changes.append({
            'table': 'category_booth_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    # 4. Zachycení rolí zaměstnanců pro tento stánek
    roles = cur.execute(
        'SELECT * FROM employee_event_booth_roles WHERE booth_id = %s',
        (booth_id,)
    ).fetchall()
    for role in roles:
        changes.append({
            'table': 'employee_event_booth_roles',
            'old_values': convert_dict_to_serializable(dict(role)),
            'new_values': None
        })

    return changes


def capture_product_cascade(cur: Cursor, product_id) -> List[dict]:
    """Zachytí všechna data ovlivněná smazáním produktu.

    Vrátí seznam změnových záznamů pro sledování undo.
    Zachycuje: produkt, vazební tabulky (product_booth_link, category_product_link).
    """
    changes = []

    # 1. Zachycení produktu
    product = cur.execute(
        'SELECT * FROM products WHERE id = %s AND deleted_at IS NULL',
        (product_id,)
    ).fetchone()
    if product:
        changes.append({
            'table': 'products',
            'old_values': convert_dict_to_serializable(dict(product)),
            'new_values': None
        })

    # 2. Zachycení vazeb stánků
    booth_links = cur.execute(
        'SELECT * FROM product_booth_link WHERE product_id = %s',
        (product_id,)
    ).fetchall()
    for link in booth_links:
        changes.append({
            'table': 'product_booth_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    # 3. Zachycení vazeb kategorií
    category_links = cur.execute(
        'SELECT * FROM category_product_link WHERE product_id = %s',
        (product_id,)
    ).fetchall()
    for link in category_links:
        changes.append({
            'table': 'category_product_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    return changes


def capture_category_cascade(cur: Cursor, category_id) -> List[dict]:
    """Zachytí všechna data ovlivněná smazáním kategorie.

    Vrátí seznam změnových záznamů pro sledování undo.
    Zachycuje: kategorii, vazební tabulky (category_booth_link, category_product_link).
    """
    changes = []

    # 1. Zachycení kategorie
    category = cur.execute(
        'SELECT * FROM categories WHERE id = %s AND deleted_at IS NULL',
        (category_id,)
    ).fetchone()
    if category:
        changes.append({
            'table': 'categories',
            'old_values': convert_dict_to_serializable(dict(category)),
            'new_values': None
        })

    # 2. Zachycení vazeb stánků
    booth_links = cur.execute(
        'SELECT * FROM category_booth_link WHERE category_id = %s',
        (category_id,)
    ).fetchall()
    for link in booth_links:
        changes.append({
            'table': 'category_booth_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    # 3. Zachycení vazeb produktů
    product_links = cur.execute(
        'SELECT * FROM category_product_link WHERE category_id = %s',
        (category_id,)
    ).fetchall()
    for link in product_links:
        changes.append({
            'table': 'category_product_link',
            'old_values': convert_dict_to_serializable(dict(link)),
            'new_values': None
        })

    return changes


def capture_employee_cascade(cur: Cursor, employee_id) -> List[dict]:
    """Zachytí všechna data ovlivněná smazáním zaměstnance.

    Vrátí seznam změnových záznamů pro sledování undo.
    Zachycuje: zaměstnance, role zaměstnance.
    """
    changes = []

    # 1. Zachycení zaměstnance
    employee = cur.execute(
        'SELECT * FROM employees WHERE id = %s AND deleted_at IS NULL',
        (employee_id,)
    ).fetchone()
    if employee:
        changes.append({
            'table': 'employees',
            'old_values': convert_dict_to_serializable(dict(employee)),
            'new_values': None
        })

    # 2. Zachycení rolí zaměstnanců
    roles = cur.execute(
        'SELECT * FROM employee_event_booth_roles WHERE employee_id = %s',
        (employee_id,)
    ).fetchall()
    for role in roles:
        changes.append({
            'table': 'employee_event_booth_roles',
            'old_values': convert_dict_to_serializable(dict(role)),
            'new_values': None
        })

    return changes


# def capture_user_cascade(cur: Cursor, user_id) -> list[dict]:
#     """
#     Captures all data that will be affected by deleting a user.
#     Returns list of change dicts for undo tracking.

#     Captures: user, wallets
#     """
#     changes = []

#     # 1. Capture the user
#     user = cur.execute(
#         'SELECT * FROM users WHERE id = %s AND deleted_at IS NULL',
#         (user_id,)
#     ).fetchone()
#     if user:
#         changes.append({
#             'table': 'users',
#             'old_values': convert_dict_to_serializable(dict(user)),
#             'new_values': None
#         })

#     # 2. Capture wallets (they get soft-deleted when user is deleted)
#     wallets = cur.execute(
#         'SELECT * FROM wallets WHERE owner_id = %s AND deleted_at IS NULL',
#         (user_id,)
#     ).fetchall()
#     for wallet in wallets:
#         changes.append({
#             'table': 'wallets',
#             'old_values': convert_dict_to_serializable(dict(wallet)),
#             'new_values': None
#         })

#     return changes
