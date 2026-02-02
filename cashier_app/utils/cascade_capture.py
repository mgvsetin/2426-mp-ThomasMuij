"""
Cascade capture functions for undo/redo system.
These functions capture all data that will be affected by delete operations,
allowing the changes to be undone as a single atomic action.
"""

from psycopg import Cursor
from uuid import UUID
from datetime import datetime, date, time


def _convert(value):
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
    """Convert a database row to a JSON-serializable dict with string UUIDs."""
    return {k: _convert(v) for k, v in row.items()}


def capture_event_cascade(cur: Cursor, event_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting an event.
    Returns list of change dicts for undo tracking.

    Captures: event, booths, products, categories, link tables, employee roles
    """
    changes = []

    # 1. Capture the event
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

    # 2. Capture all booths
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

    # 3. Capture all products
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

    # 4. Capture all categories
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

    # 5. Capture link tables
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
        # Capture category_product_links that reference any of our products or categories
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

    # 6. Capture employee roles
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

    return changes


def capture_booth_cascade(cur: Cursor, booth_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting a booth.
    Returns list of change dicts for undo tracking.

    Captures: booth, link tables (product_booth_link, category_booth_link), employee roles for this booth
    """
    changes = []

    # 1. Capture the booth
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

    # 2. Capture product links
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

    # 3. Capture category links
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

    # 4. Capture employee roles for this booth
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


def capture_product_cascade(cur: Cursor, product_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting a product.
    Returns list of change dicts for undo tracking.

    Captures: product, link tables (product_booth_link, category_product_link)
    """
    changes = []

    # 1. Capture the product
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

    # 2. Capture booth links
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

    # 3. Capture category links
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


def capture_category_cascade(cur: Cursor, category_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting a category.
    Returns list of change dicts for undo tracking.

    Captures: category, link tables (category_booth_link, category_product_link)
    """
    changes = []

    # 1. Capture the category
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

    # 2. Capture booth links
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

    # 3. Capture product links
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


def capture_employee_cascade(cur: Cursor, employee_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting an employee.
    Returns list of change dicts for undo tracking.

    Captures: employee, employee roles
    """
    changes = []

    # 1. Capture the employee
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

    # 2. Capture employee roles
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


def capture_user_cascade(cur: Cursor, user_id) -> list[dict]:
    """
    Captures all data that will be affected by deleting a user.
    Returns list of change dicts for undo tracking.

    Captures: user, wallets
    """
    changes = []

    # 1. Capture the user
    user = cur.execute(
        'SELECT * FROM users WHERE id = %s AND deleted_at IS NULL',
        (user_id,)
    ).fetchone()
    if user:
        changes.append({
            'table': 'users',
            'old_values': convert_dict_to_serializable(dict(user)),
            'new_values': None
        })

    # 2. Capture wallets (they get soft-deleted when user is deleted)
    wallets = cur.execute(
        'SELECT * FROM wallets WHERE user_id = %s AND deleted_at IS NULL',
        (user_id,)
    ).fetchall()
    for wallet in wallets:
        changes.append({
            'table': 'wallets',
            'old_values': convert_dict_to_serializable(dict(wallet)),
            'new_values': None
        })

    return changes
