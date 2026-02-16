"""Modul pro operaci vložení (paste) -- klonování zaměstnanců, akcí, stánků,
produktů a kategorií včetně všech vazebních tabulek."""

from uuid import UUID
import uuid
from typing import Callable
from flask import Blueprint, jsonify, url_for, request
from flask.wrappers import Response
from psycopg import IntegrityError, Cursor
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.errors import ForbiddenError, PgTryAdvisoryLockError, CanNotMakeNewEventIfNotCopyingEventError, NoValidEmployeesToCopyError
from cashier_app.undo_and_redo import save_change
from cashier_app.utils.cascade_capture import convert_dict_to_serializable
from cashier_app.utils.query_builder import build_insert_statement, get_insert_placeholders_and_params
from cashier_app.utils.general import get_employee_lock_key


def change_keys_make_values_UUID(from_dict: dict[str, list[str]], old_to_new_keys_dict: dict[str, str]) -> dict[str, list[UUID]]:
    """Přemapuje klíče slovníku podle old_to_new_keys_dict a hodnoty převede na UUID."""
    new_dict = {}
    for old_key, new_key in old_to_new_keys_dict.items():
        new_dict[new_key] = [UUID(id) for id in from_dict[old_key]]
    return new_dict


def make_unique_name(original_name: str, other_names_lower: set[str]) -> str:
    """Vrátí unikátní název přidáním přípony _copy / _copyN, pokud název již existuje."""
    new_name = original_name
    i = 0
    while new_name.lower() in other_names_lower:
        i += 1
        new_name = f"{original_name}_copy" if i == 1 else f"{original_name}_copy{i}"
    return new_name


# ---------------------------------------------------------------------------
# Pomocné funkce
# ---------------------------------------------------------------------------

def rows_to_changes(table: str, rows: list[dict]) -> list[dict]:
    """Převede výsledky RETURNING * na záznamy změn pro undo/redo (INSERTy)."""
    return [
        {'table': table, 'old_values': None, 'new_values': convert_dict_to_serializable(dict(row))}
        for row in rows
    ]


def insert_and_track(cur: Cursor, table: str, rows: list[dict], changes: list[dict],
                     on_conflict_do_nothing: bool | list[str] = False) -> list[dict]:
    """Vloží řádky pomocí INSERT s RETURNING *, přidá záznamy změn do seznamu changes. Vrátí vložené řádky."""
    if not rows:
        return []
    sql, query_params = build_insert_statement(table, rows, returning='*',
                                               on_conflict_do_nothing=on_conflict_do_nothing)
    inserted = cur.execute(sql, query_params).fetchall()
    changes.extend(rows_to_changes(table, inserted))
    return inserted


IdMap = dict[UUID, set[UUID]]


def clone_entities(
    directly_copied: list[dict],
    indirectly_copied: list[dict],
    target_event_id: UUID,
    source_event_id: UUID | None,
    name_column: str,
    row_builder: Callable[[dict, UUID, str, UUID], dict],
    existing_names_lower: set[str],
) -> tuple[list[dict], IdMap]:
    """
    Sestaví klonované řádky pro jednu cílovou akci.

    Vrací (rows_to_insert, id_map), kde id_map mapuje old_id -> množinu new_ids.
    - Přímo zkopírované: vždy klonovat.
    - Nepřímo zkopírované, stejná akce: identity-map (znovu použít).
    - Nepřímo zkopírované, jiná akce: klonovat.
    """
    id_map: IdMap = {}
    rows_to_insert: list[dict] = []

    for entity in directly_copied:
        if source_event_id is not None and entity['event_id'] != source_event_id:
            # nové akce -> zkopíruj data jen z jedné
            continue

        new_name = make_unique_name(entity[name_column], existing_names_lower)
        existing_names_lower.add(new_name.lower())

        new_id = uuid.uuid4()
        id_map.setdefault(entity['id'], set()).add(new_id)
        rows_to_insert.append(row_builder(entity, new_id, new_name, target_event_id))

    for entity in indirectly_copied:
        if source_event_id is not None and entity['event_id'] != source_event_id:
            continue

        if entity['event_id'] == target_event_id:
            id_map.setdefault(entity['id'], set()).add(entity['id'])
            continue

        if entity['id'] in id_map:
            continue

        new_name = make_unique_name(entity[name_column], existing_names_lower)
        existing_names_lower.add(new_name.lower())

        new_id = uuid.uuid4()
        id_map.setdefault(entity['id'], set()).add(new_id)
        rows_to_insert.append(row_builder(entity, new_id, new_name, target_event_id))

    return rows_to_insert, id_map


def clone_link_table(original_links: list[dict], id_map: IdMap,
                     col_a: str, col_b: str) -> list[dict]:
    """Vygeneruje nové řádky vazební tabulky kartézským součinem záznamů z id_map."""
    new_links: list[dict] = []
    seen: set[tuple] = set()

    for link in original_links:
        a_id = link[col_a]
        b_id = link[col_b]
        mapped_as = id_map.get(a_id, set())
        mapped_bs = id_map.get(b_id, set())
        if not mapped_as or not mapped_bs:
            continue
        for new_a in mapped_as:
            for new_b in mapped_bs:
                if (new_a, new_b) == (a_id, b_id):
                    continue
                pair = (new_a, new_b)
                if pair in seen:
                    continue
                seen.add(pair)
                new_links.append({col_a: new_a, col_b: new_b})

    return new_links


def merge_id_maps(*maps: IdMap) -> IdMap:
    """Merge multiple id_maps into one."""
    merged: IdMap = {}
    for m in maps:
        for old_id, new_ids in m.items():
            merged.setdefault(old_id, set()).update(new_ids)
    return merged


# ---------------------------------------------------------------------------
# Paste: new employees
# ---------------------------------------------------------------------------

def paste_new_employees(data_to_copy: dict, logged_employee: dict) -> tuple[Response, int]:
    if not data_to_copy['employee_ids']:
        return jsonify(error='no_employees_to_copy'), 400

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                locked = cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS locked",
                    (get_employee_lock_key(logged_employee['id'], 'paste'),)
                ).fetchone()['locked']
                if not locked:
                    raise PgTryAdvisoryLockError()

                copied_employees = cur.execute(
                    '''
                    SELECT id, username, email, password_hash, is_admin
                    FROM employees
                    WHERE id = ANY(%s) AND deleted_at IS NULL
                    ''',
                    (data_to_copy['employee_ids'],)).fetchall()

                if not copied_employees:
                    raise NoValidEmployeesToCopyError()

                employee_event_booth_roles_to_copy = cur.execute(
                    '''
                    SELECT DISTINCT link.id, link.employee_id, link.event_id, link.booth_id
                    FROM employee_event_booth_roles AS link
                    JOIN employees AS em ON em.id = link.employee_id
                    JOIN events AS ev ON ev.id = link.event_id
                    LEFT JOIN booths AS bo ON bo.id = link.booth_id
                    WHERE link.employee_id = ANY(%s)
                    AND em.deleted_at IS NULL
                    AND ev.deleted_at IS NULL
                    AND bo.deleted_at IS NULL
                    ''',
                    (data_to_copy['employee_ids'],)).fetchall()

                employee_unique_columns = cur.execute(
                    'SELECT username, email FROM employees WHERE deleted_at IS NULL'
                ).fetchall()

                lower_usernames = {emp['username'].lower() for emp in employee_unique_columns}
                lower_emails = {emp['email'].lower() for emp in employee_unique_columns}

                changes: list[dict] = []
                employee_rows = []
                copied_to_created_employees: dict[UUID, UUID] = {}

                for emp in copied_employees:
                    new_username = make_unique_name(emp['username'], lower_usernames)
                    lower_usernames.add(new_username.lower())

                    new_email = emp['email']
                    i = 0
                    while new_email.lower() in lower_emails:
                        before_at, after_at = new_email.split('@')
                        i += 1
                        new_email = f"{before_at}_copy@{after_at}" if i == 1 else f"{before_at}_copy{i}@{after_at}"
                    lower_emails.add(new_email.lower())

                    new_id = uuid.uuid4()
                    copied_to_created_employees[emp['id']] = new_id

                    employee_rows.append({
                        'id': new_id,
                        'username': new_username,
                        'email': new_email,
                        'password_hash': emp['password_hash'],
                        'is_admin': emp['is_admin'],
                        'created_by': logged_employee['id']
                    })

                insert_and_track(cur, 'employees', employee_rows, changes)

                if employee_event_booth_roles_to_copy:
                    role_rows = [{
                        'employee_id': copied_to_created_employees[link['employee_id']],
                        'event_id': link['event_id'],
                        'booth_id': link['booth_id']
                    } for link in employee_event_booth_roles_to_copy]

                    insert_and_track(cur, 'employee_event_booth_roles', role_rows, changes)

                save_change(cur, changes, logged_employee['id'])

    except NoValidEmployeesToCopyError:
        return jsonify(error='no_valid_employees_to_copy'), 400
    except PgTryAdvisoryLockError:
        return jsonify(error='paste_operation_in_progress'), 409
    except IntegrityError as e:
        if 'unique_index' in str(e):
            return jsonify(error='unique_conflict'), 500
        else:
            raise

    return jsonify(), 200


# ---------------------------------------------------------------------------
# Paste: to events or booths
# ---------------------------------------------------------------------------

def paste_to_events_or_booths(data_to_copy: dict, target_ids: dict, targets_are_new_events: bool, logged_employee: dict) -> tuple[Response, int]:
    target_events = []
    target_booths = []

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                locked = cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s) AS locked",
                    (get_employee_lock_key(logged_employee['id'], 'paste'),)
                ).fetchone()['locked']
                if not locked:
                    raise PgTryAdvisoryLockError()

                # --- accessible events ---
                if logged_employee['is_admin']:
                    accessible_events_ids = {row['id'] for row in cur.execute(
                        'SELECT id FROM events WHERE deleted_at IS NULL').fetchall()}
                else:
                    accessible_events_ids = {row['id'] for row in cur.execute(
                        '''
                        SELECT ev.id FROM events AS ev
                        JOIN employee_event_booth_roles AS link ON link.event_id = ev.id
                        WHERE link.employee_id = %s AND link.booth_id IS NULL
                        AND ev.deleted_at IS NULL
                        ''',
                        (logged_employee['id'],)).fetchall()}

                # --- source events ---
                directly_copied_events = cur.execute(
                    'SELECT id, name, start_at, end_at FROM events WHERE id = ANY(%s) AND deleted_at IS NULL',
                    (data_to_copy['event_ids'],)).fetchall()

                copied_events_ids = [ev['id'] for ev in directly_copied_events]
                for eid in copied_events_ids:
                    if eid not in accessible_events_ids:
                        raise ForbiddenError()

                changes: list[dict] = []

                # --- resolve / create target events ---
                if targets_are_new_events:
                    if not directly_copied_events:
                        raise CanNotMakeNewEventIfNotCopyingEventError()

                    lower_all_event_names = {ev['name'].lower() for ev in cur.execute(
                        'SELECT name FROM events WHERE deleted_at IS NULL').fetchall()}

                    for copied_event in directly_copied_events:
                        new_event_name = make_unique_name(copied_event['name'], lower_all_event_names)
                        lower_all_event_names.add(new_event_name.lower())

                        params = {
                            'name': new_event_name,
                            'start_at': copied_event['start_at'],
                            'end_at': copied_event['end_at'],
                            'created_by': logged_employee['id']
                        }

                        sql, query_params = build_insert_statement('events', params, returning='*')

                        new_event = cur.execute(sql, query_params).fetchone()

                        changes.extend(rows_to_changes('events', [new_event]))

                        target_event = dict(new_event)
                        target_event['id_of_copied_event'] = copied_event['id']
                        target_events.append(target_event)

                        if logged_employee['is_admin']:
                            accessible_events_ids.add(new_event['id'])
                else:
                    target_events = cur.execute(
                        'SELECT id FROM events WHERE id = ANY(%s) AND deleted_at IS NULL',
                        (target_ids['event_ids'],)).fetchall()

                    target_booths = cur.execute(
                        'SELECT id, event_id, booth_type FROM booths WHERE id = ANY(%s) AND deleted_at IS NULL',
                        (target_ids['booth_ids'],)).fetchall()

                for event in target_events:
                    if event['id'] not in accessible_events_ids:
                        raise ForbiddenError()
                for booth in target_booths:
                    if booth['event_id'] not in accessible_events_ids:
                        raise ForbiddenError()

                # --- source booths ---
                directly_copied_booths = cur.execute(
                    'SELECT id, name, event_id, booth_type FROM booths WHERE id = ANY(%s) AND deleted_at IS NULL',
                    (data_to_copy['booth_ids'],)).fetchall()

                indirectly_copied_booths = cur.execute(
                    'SELECT id, name, event_id, booth_type FROM booths WHERE event_id = ANY(%s) AND deleted_at IS NULL',
                    (copied_events_ids,)).fetchall()

                copied_booths = directly_copied_booths + indirectly_copied_booths
                copied_booths_ids = [b['id'] for b in copied_booths]

                for booth in copied_booths:
                    if booth['event_id'] not in accessible_events_ids:
                        raise ForbiddenError()

                # --- source managers ---
                copied_managers = cur.execute(
                    '''
                    SELECT em.id, link.event_id
                    FROM employee_event_booth_roles AS link
                    JOIN employees AS em ON em.id = link.employee_id
                    JOIN events AS ev ON ev.id = link.event_id
                    WHERE (link.employee_id = ANY(%s) OR link.event_id = ANY(%s))
                    AND link.booth_id IS NULL AND em.deleted_at IS NULL AND ev.deleted_at IS NULL
                    ''',
                    (data_to_copy['manager_ids'], copied_events_ids)).fetchall()

                # --- source products ---
                directly_copied_products = cur.execute(
                    'SELECT id, event_id, name, price, image_id FROM products WHERE id = ANY(%s) AND deleted_at IS NULL',
                    (data_to_copy['product_ids'],)).fetchall()

                indirectly_copied_products = cur.execute(
                    '''
                    SELECT DISTINCT p.id, p.event_id, p.name, p.price, p.image_id
                    FROM products AS p
                    LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                    WHERE (p.event_id = ANY(%s) OR bo_link.booth_id = ANY(%s))
                    AND p.deleted_at IS NULL
                    ''',
                    (copied_events_ids, copied_booths_ids)).fetchall()

                for product in directly_copied_products + indirectly_copied_products:
                    if product['event_id'] not in accessible_events_ids:
                        raise ForbiddenError()

                # --- source categories ---
                directly_copied_categories = cur.execute(
                    'SELECT id, name, event_id FROM categories WHERE id = ANY(%s) AND deleted_at IS NULL',
                    (data_to_copy['category_ids'],)).fetchall()

                indirectly_copied_categories = cur.execute(
                    '''
                    SELECT DISTINCT c.id, c.name, c.event_id
                    FROM categories AS c
                    LEFT JOIN category_booth_link AS bo_link ON bo_link.category_id = c.id
                    WHERE (c.event_id = ANY(%s) OR bo_link.booth_id = ANY(%s))
                    AND c.deleted_at IS NULL
                    ''',
                    (copied_events_ids, copied_booths_ids)).fetchall()

                for category in directly_copied_categories + indirectly_copied_categories:
                    if category['event_id'] not in accessible_events_ids:
                        raise ForbiddenError()

                # =============================================================
                # PATH A: paste to events
                # =============================================================
                if target_events:
                    _paste_to_events_path(
                        cur, changes, target_events, targets_are_new_events,
                        copied_managers,
                        directly_copied_booths, indirectly_copied_booths,
                        directly_copied_products, indirectly_copied_products,
                        directly_copied_categories, indirectly_copied_categories,
                        logged_employee)

                # =============================================================
                # PATH B: paste to booths
                # =============================================================
                elif target_booths:
                    _paste_to_booths_path(
                        cur, changes, target_booths,
                        data_to_copy, copied_booths_ids,
                        directly_copied_products + indirectly_copied_products,
                        directly_copied_categories + indirectly_copied_categories,
                        logged_employee)

                save_change(cur, changes, logged_employee['id'])

    except ForbiddenError:
        return jsonify(error='insufficient_privileges'), 403
    except CanNotMakeNewEventIfNotCopyingEventError:
        return jsonify(error='can_not_make_new_event_if_not_copying_event'), 400
    except PgTryAdvisoryLockError:
        return jsonify(error='paste_operation_in_progress'), 409
    except IntegrityError as e:
        if 'unique_index' in str(e):
            return jsonify(error='unique_conflict'), 500
        else:
            raise

    return jsonify(), 200


# ---------------------------------------------------------------------------
# Path A: paste to events (new or existing)
# ---------------------------------------------------------------------------

def _paste_to_events_path(
    cur: Cursor, changes: list[dict], target_events: list[dict], targets_are_new_events: bool,
    copied_managers: list[dict],
    directly_copied_booths: list[dict], indirectly_copied_booths: list[dict],
    directly_copied_products: list[dict], indirectly_copied_products: list[dict],
    directly_copied_categories: list[dict], indirectly_copied_categories: list[dict],
    logged_employee: dict
) -> None:
    all_manager_rows = []
    all_booth_rows = []
    all_product_rows = []
    all_category_rows = []

    # {event_id: {old_id: {new_id/old_id}}}
    # set[UUID], obsahuje max 2 věci a to pokud
    # je v copied directly i indirectly a paste
    # je do eventu z kterého pohází
    id_maps_per_target: dict[UUID, dict[UUID, set[UUID]]] = {}

    def booth_builder(old: dict, new_id: UUID, new_name: str, tgt_eid: UUID) -> dict:
        return {'id': new_id, 'name': new_name, 'event_id': tgt_eid,
                'booth_type': old['booth_type'], 'created_by': logged_employee['id']}

    def product_builder(old: dict, new_id: UUID, new_name: str, tgt_eid: UUID) -> dict:
        return {'id': new_id, 'event_id': tgt_eid, 'name': new_name,
                'price': old['price'], 'image_id': old['image_id']}

    def category_builder(old: dict, new_id: UUID, new_name: str, tgt_eid: UUID) -> dict:
        return {'id': new_id, 'name': new_name, 'event_id': tgt_eid}

    for target_event in target_events:
        te_id = target_event['id']

        # jestli se vytváří nové akce, potřebuju zkopírovat data pouze z 1 zkopírované akce
        source_event_id = target_event.get('id_of_copied_event') if targets_are_new_events else None

        # --- managers ---
        if copied_managers:
            existing_manager_ids = {row['employee_id'] for row in cur.execute(
                'SELECT employee_id FROM employee_event_booth_roles WHERE event_id = %s AND booth_id IS NULL',
                (te_id,))}

            if targets_are_new_events:
                for mgr in copied_managers:
                    if mgr['event_id'] != source_event_id:
                        continue
                    all_manager_rows.append({
                        'employee_id': mgr['id'], 'event_id': te_id, 'booth_id': None})
            else:
                seen_manager_ids: set[UUID] = set()
                for mgr in copied_managers:
                    if mgr['id'] in existing_manager_ids or mgr['id'] in seen_manager_ids:
                        continue
                    seen_manager_ids.add(mgr['id'])
                    all_manager_rows.append({
                        'employee_id': mgr['id'], 'event_id': te_id, 'booth_id': None})

        # --- booths ---
        existing_booth_names = {b['name'].lower() for b in cur.execute(
            'SELECT name FROM booths WHERE event_id = %s AND deleted_at IS NULL',
            (te_id,)).fetchall()}

        booth_rows, booth_map = clone_entities(
            directly_copied_booths, indirectly_copied_booths,
            te_id, source_event_id, 'name', booth_builder, existing_booth_names)
        all_booth_rows.extend(booth_rows)

        # --- products ---
        existing_product_names = {p['name'].lower() for p in cur.execute(
            'SELECT name FROM products WHERE event_id = %s AND deleted_at IS NULL',
            (te_id,)).fetchall()}

        product_rows, product_map = clone_entities(
            directly_copied_products, indirectly_copied_products,
            te_id, source_event_id, 'name', product_builder, existing_product_names)
        all_product_rows.extend(product_rows)

        # --- categories ---
        existing_category_names = {c['name'].lower() for c in cur.execute(
            'SELECT name FROM categories WHERE event_id = %s AND deleted_at IS NULL',
            (te_id,)).fetchall()}

        category_rows, category_map = clone_entities(
            directly_copied_categories, indirectly_copied_categories,
            te_id, source_event_id, 'name', category_builder, existing_category_names)
        all_category_rows.extend(category_rows)

        id_maps_per_target[te_id] = merge_id_maps(booth_map, product_map, category_map)

    # --- bulk inserts: managers (CTE), booths, products, categories ---
    if all_manager_rows:
        cols = ['employee_id', 'event_id', 'booth_id']
        placeholders, params = get_insert_placeholders_and_params(all_manager_rows, cols)
        inserted = cur.execute(
            f'''
            WITH input_data AS (
            VALUES {placeholders.as_string(cur)}
            ),
            input_with_cols AS (
            SELECT
                column1::uuid AS {cols[0]},
                column2::uuid AS {cols[1]},
                column3::uuid AS {cols[2]}
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
            SELECT * FROM valid_rows
            RETURNING *''',
            params).fetchall()
        changes.extend(rows_to_changes('employee_event_booth_roles', inserted))

    insert_and_track(cur, 'booths', all_booth_rows, changes)
    insert_and_track(cur, 'products', all_product_rows, changes)
    insert_and_track(cur, 'categories', all_category_rows, changes)

    # --- fetch original link rows ---
    all_copied_ids = set()
    for m in id_maps_per_target.values():
        all_copied_ids.update(m.keys())
    all_copied_ids = list(all_copied_ids)

    employee_booth_roles_to_copy = cur.execute(
        '''
        SELECT link.booth_id, link.employee_id, link.event_id
        FROM employee_event_booth_roles AS link
        JOIN employees em ON em.id = link.employee_id
        WHERE booth_id = ANY(%s) AND em.deleted_at IS NULL
        ''',
        (all_copied_ids,)).fetchall()

    product_booth_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.booth_id, link.product_id, bo.event_id
        FROM product_booth_link AS link
        JOIN booths AS bo ON bo.id = link.booth_id
        WHERE link.booth_id = ANY(%s) OR link.product_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    category_booth_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.booth_id, link.category_id, bo.event_id
        FROM category_booth_link AS link
        JOIN booths AS bo ON bo.id = link.booth_id
        WHERE link.booth_id = ANY(%s) OR link.category_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    category_product_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.product_id, link.category_id, pr.event_id
        FROM category_product_link AS link
        JOIN products AS pr ON pr.id = link.product_id
        WHERE link.product_id = ANY(%s) OR link.category_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    # --- clone links per target event ---
    all_eebr_rows = []
    all_pb_rows = []
    all_cb_rows = []
    all_cp_rows = []

    for target_event in target_events:
        te_id = target_event['id']
        id_map = id_maps_per_target[te_id]

        # identity-map entities in target event that are referenced by links but not yet in id_map,
        # so clone_link_table can create links between cloned and existing entities
        for row in product_booth_links_to_copy:
            if row['event_id'] == te_id:
                id_map.setdefault(row['booth_id'], set()).add(row['booth_id'])
                id_map.setdefault(row['product_id'], set()).add(row['product_id'])
        for row in category_booth_links_to_copy:
            if row['event_id'] == te_id:
                id_map.setdefault(row['booth_id'], set()).add(row['booth_id'])
                id_map.setdefault(row['category_id'], set()).add(row['category_id'])
        for row in category_product_links_to_copy:
            if row['event_id'] == te_id:
                id_map.setdefault(row['product_id'], set()).add(row['product_id'])
                id_map.setdefault(row['category_id'], set()).add(row['category_id'])

        # employee x booth roles
        for row in employee_booth_roles_to_copy:
            for new_booth_id in id_map.get(row['booth_id'], set()):
                if new_booth_id != row['booth_id']:
                    all_eebr_rows.append({
                        'employee_id': row['employee_id'],
                        'event_id': te_id,
                        'booth_id': new_booth_id
                    })

        all_pb_rows.extend(clone_link_table(product_booth_links_to_copy, id_map, 'booth_id', 'product_id'))
        all_cb_rows.extend(clone_link_table(category_booth_links_to_copy, id_map, 'booth_id', 'category_id'))
        all_cp_rows.extend(clone_link_table(category_product_links_to_copy, id_map, 'product_id', 'category_id'))

    # --- bulk insert link rows ---
    if all_eebr_rows:
        cols = ['employee_id', 'event_id', 'booth_id']
        placeholders, params = get_insert_placeholders_and_params(all_eebr_rows, cols)
        inserted = cur.execute(
            f'''
            WITH input_data AS (
            VALUES {placeholders.as_string(cur)}
            ),
            input_with_cols AS (
            SELECT
                column1::uuid AS {cols[0]},
                column2::uuid AS {cols[1]},
                column3::uuid AS {cols[2]}
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
                    AND link.booth_id IS NULL
                )
            )
            INSERT INTO employee_event_booth_roles (booth_id, employee_id, event_id)
            SELECT booth_id, employee_id, event_id FROM valid_rows
            ON CONFLICT DO NOTHING
            RETURNING *''',
            params).fetchall()
        changes.extend(rows_to_changes('employee_event_booth_roles', inserted))

    insert_and_track(cur, 'product_booth_link', all_pb_rows, changes, on_conflict_do_nothing=True)
    insert_and_track(cur, 'category_booth_link', all_cb_rows, changes, on_conflict_do_nothing=True)
    insert_and_track(cur, 'category_product_link', all_cp_rows, changes, on_conflict_do_nothing=True)


# ---------------------------------------------------------------------------
# Path B: paste to booths
# ---------------------------------------------------------------------------

def _paste_to_booths_path(
    cur: Cursor, changes: list[dict], target_booths: list[dict],
    data_to_copy: dict, copied_booths_ids: list[UUID],
    copied_products: list[dict], copied_categories: list[dict],
    logged_employee: dict
) -> None:
    target_booths_by_event: dict[UUID, list[dict]] = {}
    for t_booth in target_booths:
        target_booths_by_event.setdefault(t_booth['event_id'], []).append(t_booth)

    product_rows = []
    category_rows = []
    id_maps_per_event: dict[UUID, dict[UUID, set[UUID]]] = {}

    for event_id in target_booths_by_event:
        product_map: dict[UUID, set[UUID]] = {}
        category_map: dict[UUID, set[UUID]] = {}

        # --- existing names for uniqueness ---
        existing_product_names = {p['name'].lower() for p in cur.execute(
            'SELECT name FROM products WHERE event_id = %s AND deleted_at IS NULL',
            (event_id,)).fetchall()}

        existing_category_names = {c['name'].lower() for c in cur.execute(
            'SELECT name FROM categories WHERE event_id = %s AND deleted_at IS NULL',
            (event_id,)).fetchall()}

        for product in copied_products:
            if product['event_id'] == event_id:
                product_map.setdefault(product['id'], set()).add(product['id'])
                continue
            if product['id'] in product_map:
                continue

            new_name = make_unique_name(product['name'], existing_product_names)
            existing_product_names.add(new_name.lower())

            new_id = uuid.uuid4()
            product_map.setdefault(product['id'], set()).add(new_id)
            product_rows.append({
                'id': new_id, 'event_id': event_id, 'name': new_name,
                'price': product['price'], 'image_id': product['image_id']
            })

        for category in copied_categories:
            if category['event_id'] == event_id:
                category_map.setdefault(category['id'], set()).add(category['id'])
                continue
            if category['id'] in category_map:
                continue

            new_name = make_unique_name(category['name'], existing_category_names)
            existing_category_names.add(new_name.lower())

            new_id = uuid.uuid4()
            category_map.setdefault(category['id'], set()).add(new_id)
            category_rows.append({
                'id': new_id, 'name': new_name, 'event_id': event_id
            })

        id_maps_per_event[event_id] = merge_id_maps(product_map, category_map)

    insert_and_track(cur, 'products', product_rows, changes)
    insert_and_track(cur, 'categories', category_rows, changes)

    # --- fetch original links ---
    all_copied_ids = list(set(copied_booths_ids)
                          | {p['id'] for p in copied_products}
                          | {c['id'] for c in copied_categories})

    employee_booth_roles_to_copy = cur.execute(
        '''
        SELECT booth_id, employee_id, event_id
        FROM employee_event_booth_roles
        WHERE booth_id = ANY(%s) OR employee_id = ANY(%s)
        ''',
        (all_copied_ids, data_to_copy['employees_to_assign_to_target_booths'])).fetchall()

    product_booth_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.booth_id, link.product_id, bo.event_id
        FROM product_booth_link AS link
        JOIN booths AS bo ON bo.id = link.booth_id
        WHERE link.booth_id = ANY(%s) OR link.product_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    category_booth_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.booth_id, link.category_id, bo.event_id
        FROM category_booth_link AS link
        JOIN booths AS bo ON bo.id = link.booth_id
        WHERE link.booth_id = ANY(%s) OR link.category_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    category_product_links_to_copy = cur.execute(
        '''
        SELECT DISTINCT link.product_id, link.category_id, pr.event_id
        FROM category_product_link AS link
        JOIN products AS pr ON pr.id = link.product_id
        WHERE link.product_id = ANY(%s) OR link.category_id = ANY(%s)
        ''',
        (all_copied_ids, all_copied_ids)).fetchall()

    # --- build link rows per target booth ---
    eebr_rows = []
    pb_rows = []
    cb_rows = []
    cp_rows = []

    for t_booth in target_booths:
        eid = t_booth['event_id']
        id_map = id_maps_per_event.get(eid, {})

        # employees x booths
        for row in employee_booth_roles_to_copy:
            if row['booth_id'] == t_booth['id']:
                continue
            eebr_rows.append({
                'employee_id': row['employee_id'],
                'event_id': eid,
                'booth_id': t_booth['id']
            })

        if t_booth['booth_type'] == 'seller':
            # products x booths
            for row in product_booth_links_to_copy:
                new_product_id = next(iter(id_map.get(row['product_id'], set())), None)
                if new_product_id and not (row['booth_id'] == t_booth['id'] and row['product_id'] == new_product_id):
                    pb_rows.append({'product_id': new_product_id, 'booth_id': t_booth['id']})

            # categories x booths
            for row in category_booth_links_to_copy:
                new_category_id = next(iter(id_map.get(row['category_id'], set())), None)
                if new_category_id and not (row['booth_id'] == t_booth['id'] and row['category_id'] == new_category_id):
                    cb_rows.append({'category_id': new_category_id, 'booth_id': t_booth['id']})

        # products x categories
        for row in category_product_links_to_copy:
            new_product_id = next(iter(id_map.get(row['product_id'], set())), None)
            new_category_id = next(iter(id_map.get(row['category_id'], set())), None)
            if (new_product_id and new_category_id
                    and not (row['product_id'] == new_product_id and row['category_id'] == new_category_id)):
                cp_rows.append({'category_id': new_category_id, 'product_id': new_product_id})

    # --- bulk insert link rows ---
    if eebr_rows:
        cols = ['employee_id', 'event_id', 'booth_id']
        placeholders, params = get_insert_placeholders_and_params(eebr_rows, cols)
        inserted = cur.execute(
            f'''
            WITH input_data AS (
            VALUES {placeholders.as_string(cur)}
            ),
            input_with_cols AS (
            SELECT
                column1::uuid AS {cols[0]},
                column2::uuid AS {cols[1]},
                column3::uuid AS {cols[2]}
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
                    AND link.booth_id IS NULL
                )
            )
            INSERT INTO employee_event_booth_roles (booth_id, employee_id, event_id)
            SELECT booth_id, employee_id, event_id FROM valid_rows
            ON CONFLICT DO NOTHING
            RETURNING *''',
            params).fetchall()
        changes.extend(rows_to_changes('employee_event_booth_roles', inserted))

    insert_and_track(cur, 'product_booth_link', pb_rows, changes, on_conflict_do_nothing=True)
    insert_and_track(cur, 'category_booth_link', cb_rows, changes, on_conflict_do_nothing=True)
    insert_and_track(cur, 'category_product_link', cp_rows, changes, on_conflict_do_nothing=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def do_paste(data_to_copy: dict, target_ids: dict, targets_are_new_employees: bool, targets_are_new_events: bool, logged_employee: dict) -> tuple[Response, int]:
    if targets_are_new_employees:
        return paste_new_employees(data_to_copy, logged_employee)
    return paste_to_events_or_booths(data_to_copy, target_ids, targets_are_new_events, logged_employee)


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------

api_bp = Blueprint('paste_api', __name__, url_prefix='/api/paste')


@api_bp.route('', methods=('POST',))
def paste():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not request.is_json:
        return jsonify(error='invalid_mimetype'), 400

    data: dict | None = request.get_json(silent=True)

    if data is None:
        return jsonify(error='invalid_request_body'), 400

    frontend_targets = data.get('targets')

    if not frontend_targets:
        return jsonify(error='missing_targets'), 400

    if frontend_targets in ['newEvents', 'newEmployees'] and not logged_employee['is_admin']:
        return jsonify(error='insufficient_privileges'), 403

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

        if (not frontend_targets['eventIds']
            and not frontend_targets['boothIds']):
            return jsonify(error='missing_targets'), 400

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
        and 'employeesToAssignToTargetBooths' not in data_to_copy_keys
        and 'employeeIds' not in data_to_copy_keys):
        return jsonify(error='invalid_data_to_copy'), 400

    if (not isinstance(frontend_data_to_copy['eventIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['boothIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['productIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['categoryIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['managerIds'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['employeesToAssignToTargetBooths'], (list, tuple, set))
        or not isinstance(frontend_data_to_copy['employeeIds'], (list, tuple, set))):
        return jsonify(error='invalid_data_to_copy'), 400

    try:
        data_to_copy = change_keys_make_values_UUID(frontend_data_to_copy, {
            'eventIds': 'event_ids',
            'boothIds': 'booth_ids',
            'productIds': 'product_ids',
            'categoryIds': 'category_ids',
            'managerIds': 'manager_ids',
            'employeesToAssignToTargetBooths': 'employees_to_assign_to_target_booths',
            'employeeIds': 'employee_ids'})
    except (ValueError, TypeError):
        return jsonify(error='invalid_data_to_copy'), 400

    return do_paste(data_to_copy, target_ids, targets_are_new_employees, targets_are_new_events, logged_employee)
