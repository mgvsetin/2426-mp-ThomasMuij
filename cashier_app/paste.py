from typing import Sequence, Tuple, Any, Literal
import os
from datetime import timezone
from dateutil import parser
from dataclasses import dataclass, field, asdict, fields
from flask import Blueprint, current_app, jsonify, url_for, session, request
from uuid import UUID
import uuid
from collections.abc import Mapping, Iterable
from datetime import datetime
from psycopg import IntegrityError
from psycopg.errors import ForeignKeyViolation
from psycopg.types.json import Jsonb
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.utils.events import validate_event_or_booth_name
from cashier_app.utils.products import validate_product_or_category_name, validate_product_price, image_extension_is_allowed, verify_image_file_get_info, save_unique_stream, convert_image_paths_from_relative
from cashier_app.utils.employees_users import is_manager
from cashier_app.utils.products import convert_image_paths_from_relative


class ForbiddenError(Exception):
    pass

class CanNotMakeNewEventIfNotCopyingEvent(Exception):
    pass

class NoValidEmployeesToCopy(Exception):
    pass

class NoPasteToUndo(Exception):
    pass

class NoPasteToRedo(Exception):
    pass


def change_keys_make_values_UUID(from_dict: dict[str, list[str]], old_to_new_keys_dict: dict[str, str]):
    new_dict = {}
    for old_key, new_key in old_to_new_keys_dict.items():
        new_dict[new_key] = [UUID(id) for id in from_dict[old_key]]
    return new_dict


def make_unique_name(original_name: str, other_names_lower: set[str]) -> str:
    new_name = original_name
    i = 0
    while new_name.lower() in other_names_lower:
        i += 1
        new_name = f"{original_name}_copy" if i == 1 else f"{original_name}_copy{i}"
    
    return new_name


def get_placeholders_and_params(rows: Sequence[Tuple[Any, ...]]) -> Tuple[str, list]:
    """
    Build SQL multi-row placeholders and a flat params list.

    Example:
      rows = [(1, 'a'), (2, 'b')]
      -> placeholders = '(%s,%s),(%s,%s)'
         params = [1, 'a', 2, 'b']

    Returns:
      (placeholders_string, flat_params_list)
    """
    # handle empty input
    if not rows:
        return "", []

    # ensure every row has same length
    row_len = len(rows[0])
    if any(len(row) != row_len for row in rows):
        raise ValueError("All rows must have the same number of columns")

    placeholders_for_row = "(" + ",".join(["%s"] * row_len) + ")"
    placeholders = ",".join([placeholders_for_row] * len(rows))
    params = [item for row in rows for item in row]

    return placeholders, params


def get_delete_columns_placeholders_and_params(rows_to_delete: list[dict]):
    columns_list = list(rows_to_delete[0].keys())
    columns = '(' + ', '.join(columns_list) + ')'


    placeholders = []
    params = []
    for row in rows_to_delete:
        placeholders.append(f"({', '.join(['%s'] * len(columns_list))})")
        params.extend([row[col] for col in columns_list])

    placeholders = ', '.join(placeholders)

    return columns, placeholders, params


def convert_uuids_to_str(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: convert_uuids_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_uuids_to_str(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(convert_uuids_to_str(v) for v in obj)
    return obj


# def convert_str_to_uuids(obj: Any) -> Any:
#     if isinstance(obj, str):
#         try:
#             return UUID(obj)
#         except (ValueError, TypeError):
#             return obj
#     # dict/list/tuple recursion
#     if isinstance(obj, dict):
#         return {k: convert_str_to_uuids(v) for k, v in obj.items()}
#     if isinstance(obj, list):
#         return [convert_str_to_uuids(v) for v in obj]
#     if isinstance(obj, tuple):
#         return tuple(convert_str_to_uuids(v) for v in obj)
#     return obj


def wrap_for_mutation(obj):
    """Return a wrapped object that will auto-convert future mutations:
       - dict -> StrDict
       - list/tuple -> StrList (tuples become tuple of wrapped values)
       - str -> uuid.UUID
       - otherwise -> as-is
    """
    if isinstance(obj, str):
        try:
            return UUID(obj)
        except (ValueError, TypeError):
            return obj
    if isinstance(obj, StrDict) or isinstance(obj, StrList):
        return obj
    if isinstance(obj, Mapping):
        return StrDict(obj)
    if isinstance(obj, list):
        return StrList(obj)
    if isinstance(obj, tuple):
        return tuple(wrap_for_mutation(x) for x in obj)
    if isinstance(obj, (str, bytes)):
        return obj
    return obj


class StrDict(dict):
    def __init__(self, mapping=None, **kwargs):
        mapping = mapping or {}
        super().__init__()

        for k, v in dict(mapping, **kwargs).items():
            self[k] = v

    def __setitem__(self, key, value):
        if isinstance(key, str):
            try:
                key = UUID(key)
            except (ValueError, TypeError):
                pass
        super().__setitem__(key, wrap_for_mutation(value))

    def update(self, mapping=(), **kwargs):
        for k, v in dict(mapping, **kwargs).items():
            self[k] = v

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        self[key] = default
        return self[key]


class StrList(list):
    def __init__(self, iterable=()):
        super().__init__(wrap_for_mutation(x) for x in iterable)

    def append(self, value):
        super().append(wrap_for_mutation(value))

    def extend(self, iterable):
        super().extend(wrap_for_mutation(x) for x in iterable)

    def insert(self, index, value):
        super().insert(index, wrap_for_mutation(value))

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            wrapped = [wrap_for_mutation(x) for x in value]
            super().__setitem__(index, wrapped)
        else:
            super().__setitem__(index, wrap_for_mutation(value))

    def __iadd__(self, other):
        self.extend(other)
        return self




@dataclass
class CopyPasteRow:
    performed_by: UUID

    targets_were_new_employees: bool = False
    targets_were_new_events: bool = False

    id: UUID | None = None

    target_event_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})
    target_booth_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})

    data_to_copy: dict[str, Any] = field(default_factory=dict, metadata={'convert_uuids': True})

    event_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})
    booth_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})
    product_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})
    category_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})
    employee_ids: list[UUID] = field(default_factory=list, metadata={'convert_uuids': True})

    employee_event_booth_roles_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
    product_booth_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
    category_booth_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})
    category_product_link_rows: list[dict[str, Any]] = field(default_factory=list, metadata={'convert_uuids': True})

    occurred_at: datetime | None = None


    def __post_init__(self):
        for f in fields(self):
            if f.metadata.get('convert_uuids'):
                original = getattr(self, f.name)
                wrapped = wrap_for_mutation(original)
                setattr(self, f.name, wrapped)


    def to_params(self):
        return {
            'performed_by': self.performed_by,

            'targets_were_new_employees': self.targets_were_new_employees,
            'targets_were_new_events': self.targets_were_new_events,

            'target_event_ids': Jsonb(convert_uuids_to_str(self.target_event_ids)),
            'target_booth_ids': Jsonb(convert_uuids_to_str(self.target_booth_ids)),

            'data_to_copy': Jsonb(convert_uuids_to_str(self.data_to_copy)),

            'event_ids': Jsonb(convert_uuids_to_str(self.event_ids)),
            'booth_ids': Jsonb(convert_uuids_to_str(self.booth_ids)),
            'product_ids': Jsonb(convert_uuids_to_str(self.product_ids)),
            'category_ids': Jsonb(convert_uuids_to_str(self.category_ids)),
            'employee_ids': Jsonb(convert_uuids_to_str(self.employee_ids)),

            'employee_event_booth_roles_rows': Jsonb(convert_uuids_to_str(self.employee_event_booth_roles_rows)),
            'product_booth_link_rows': Jsonb(convert_uuids_to_str(self.product_booth_link_rows)),
            'category_booth_link_rows': Jsonb(convert_uuids_to_str(self.category_booth_link_rows)),
            'category_product_link_rows': Jsonb(convert_uuids_to_str(self.category_product_link_rows))
        }


def save_copy_paste(row: CopyPasteRow):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO copy_paste_history
                    (performed_by,

                    targets_were_new_employees,
                    targets_were_new_events,

                    target_event_ids,
                    target_booth_ids,

                    data_to_copy,

                    event_ids,
                    booth_ids,
                    product_ids,
                    category_ids,
                    employee_ids,

                    employee_event_booth_roles_rows,
                    product_booth_link_rows,
                    category_booth_link_rows,
                    category_product_link_rows)
                VALUES (
                    %(performed_by)s,

                    %(targets_were_new_employees)s,
                    %(targets_were_new_events)s,

                    %(target_event_ids)s,
                    %(target_booth_ids)s,

                    %(data_to_copy)s,

                    %(event_ids)s,
                    %(booth_ids)s,
                    %(product_ids)s,
                    %(category_ids)s,
                    %(employee_ids)s,

                    %(employee_event_booth_roles_rows)s,
                    %(product_booth_link_rows)s,
                    %(category_booth_link_rows)s,
                    %(category_product_link_rows)s)
                ''',
                row.to_params())


def do_paste(data_to_copy, target_ids, targets_are_new_employees, targets_are_new_events, logged_employee):
    copy_paste_row = CopyPasteRow(
        performed_by=logged_employee['id'],
        targets_were_new_employees=targets_are_new_employees,
        targets_were_new_events=targets_are_new_events,
        target_event_ids=target_ids['event_ids'],
        target_booth_ids=target_ids['booth_ids'],
        data_to_copy=data_to_copy
        )


    if targets_are_new_employees:
        if not data_to_copy['employee_ids']:
            return jsonify(error='no_employees_to_copy'), 400
        
        try:
            with get_pool().connection() as conn:
                with conn.cursor() as cur:                
                    copied_employees = cur.execute(
                        '''
                        SELECT id, username, email, password_hash, is_admin
                        FROM employees
                        WHERE id = ANY(%s)
                        AND is_admin IS FALSE
                        AND deleted_at IS NULL
                        ''',
                        (data_to_copy['employee_ids'],)).fetchall()
                    
                    if not copied_employees:
                        raise NoValidEmployeesToCopy()
                    
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
                    '''
                    SELECT username, email
                    FROM employees
                    WHERE deleted_at IS NULL
                    ''',
                    ).fetchall()

                    lower_employee_usernames = {emp['username'].lower() for emp in employee_unique_columns}
                    lower_employee_email = {emp['email'].lower() for emp in employee_unique_columns}

                    employee_rows = []
                    copied_to_created_employees = {}
                    
                    for employee_to_copy in copied_employees:                        
                        new_employee_username = make_unique_name(employee_to_copy['username'], lower_employee_usernames)
                        lower_employee_usernames.add(new_employee_username.lower())

                        new_employee_email = employee_to_copy['email']
                        i = 0
                        while new_employee_email.lower() in lower_employee_email:
                            before_at_sign, after_at_sign = new_employee_email.split('@')
                            i += 1
                            new_employee_email = f"{before_at_sign}_copy@{after_at_sign}" if i == 1 else f"{before_at_sign}_copy{i}@{after_at_sign}"

                        new_id = uuid.uuid4()
                        copied_to_created_employees[employee_to_copy['id']] = new_id

                        employee_rows.append((
                            new_id,
                            new_employee_username,
                            new_employee_email,
                            employee_to_copy['password_hash'],
                            employee_to_copy['is_admin'],
                            logged_employee['id']
                        ))

                        copy_paste_row.employee_ids.append(new_id)

                    placeholders, params = get_placeholders_and_params(employee_rows)

                    cur.execute(
                        f'''
                        INSERT INTO employees
                        (id, username, email, password_hash, is_admin, created_by)
                        VALUES {placeholders}
                        ''',
                        params)
                        
                    if employee_event_booth_roles_to_copy:
                        rows = [(copied_to_created_employees[link['employee_id']], link['event_id'], link['booth_id']) for link in employee_event_booth_roles_to_copy]

                        placeholders, params = get_placeholders_and_params(rows)

                        cur.execute(
                            f'''
                            INSERT INTO employee_event_booth_roles
                            (employee_id, event_id, booth_id)
                            VALUES {placeholders}
                            ''',
                            params)
                        
                    save_copy_paste(copy_paste_row)

        except NoValidEmployeesToCopy:
            return jsonify(error='no_valid_employees_to_copy'), 400

        return jsonify(), 200


    target_events = []
    target_booths = []

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                if logged_employee['is_admin']:
                    accessible_events_ids_for_logged_employee = cur.execute(
                    '''
                    SELECT id
                    FROM events
                    WHERE deleted_at IS NULL
                    '''
                ).fetchall()
                else:
                    accessible_events_ids_for_logged_employee = cur.execute(
                        '''
                        SELECT ev.id
                        FROM events AS ev
                        JOIN employee_event_booth_roles AS link ON link.event_id = ev.id
                        WHERE link.employee_id = %s
                        AND link.booth_id IS NULL
                        AND ev.deleted_at IS NULL
                        ''',
                        (logged_employee['id'],)).fetchall()
                
                accessible_events_ids_for_logged_employee = {event['id'] for event in accessible_events_ids_for_logged_employee}

                directly_copied_events = cur.execute(
                    '''
                    SELECT id, name, start_at, end_at
                    FROM events
                    WHERE id = ANY(%s)
                    AND deleted_at IS NULL
                    ''',
                    (data_to_copy['event_ids'],)).fetchall()

                copied_events_ids = [event['id'] for event in directly_copied_events]


                for event_id in copied_events_ids:
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()


                if targets_are_new_events:
                    if not directly_copied_events:
                        raise CanNotMakeNewEventIfNotCopyingEvent()

                    lower_all_event_names = cur.execute(
                        '''
                        SELECT name
                        FROM events
                        WHERE deleted_at IS NULL
                        ''',
                        ).fetchall()
                    
                    lower_all_event_names = {event['name'].lower() for event in lower_all_event_names}
                    
                    for copied_event in directly_copied_events:
                        new_event_name = make_unique_name(copied_event['name'], lower_all_event_names)
                        lower_all_event_names.add(new_event_name.lower())
                        
                        target_event = cur.execute(
                            '''
                            INSERT INTO events
                            (name, start_at, end_at, created_by)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                            ''',
                            (new_event_name, copied_event['start_at'], copied_event['end_at'], logged_employee['id'])).fetchone()
                        
                        copy_paste_row.event_ids.append(target_event['id'])

                        target_event['id_of_copied_event'] = copied_event['id']
                        
                        target_events.append(target_event)
                        if logged_employee['is_admin']:
                            accessible_events_ids_for_logged_employee.add(target_event['id'])
                else:
                    target_events = cur.execute(
                        '''
                        SELECT id
                        FROM events
                        WHERE id = ANY(%s)
                        AND deleted_at IS NULL
                        ''',
                        (target_ids['event_ids'],)).fetchall()
                    
                    target_booths = cur.execute(
                        '''
                        SELECT id, event_id, booth_type
                        FROM booths
                        WHERE id = ANY(%s)
                        AND deleted_at IS NULL
                        ''',
                        (target_ids['booth_ids'],)).fetchall()

                for event in target_events:
                    event_id = event['id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                for booth in target_booths:
                    event_id = booth['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                directly_copied_booths = cur.execute(
                    '''
                    SELECT id, name, event_id, booth_type
                    FROM booths
                    WHERE id = ANY(%s)
                    AND deleted_at IS NULL
                    ''',
                    (data_to_copy['booth_ids'],)).fetchall()
                
                indirectly_copied_booths = cur.execute(
                    '''
                    SELECT id, name, event_id, booth_type
                    FROM booths
                    WHERE event_id = ANY(%s)
                    AND deleted_at IS NULL
                    ''',
                    (copied_events_ids,)).fetchall()
                
                copied_booths = directly_copied_booths + indirectly_copied_booths

                copied_booths_ids = [booth['id'] for booth in copied_booths]

                for booth in copied_booths:
                    event_id = booth['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()

                # do the name uniqueness thing at the inserts

                copied_managers = cur.execute(
                    '''
                    SELECT e.id, link.event_id
                    FROM employee_event_booth_roles AS link
                    JOIN employees AS e ON e.id = link.employee_id
                    WHERE (link.employee_id = ANY(%s)
                        OR link.event_id = ANY(%s))
                    AND link.booth_id IS NULL
                    AND e.deleted_at IS NULL
                    ''',
                    (data_to_copy['manager_ids'], copied_events_ids)).fetchall()

                
                directly_copied_products = cur.execute(
                    '''
                    SELECT id, event_id, name, price, image_id
                    FROM products
                    WHERE id = ANY(%s)
                    ''',
                    (data_to_copy['product_ids'],)).fetchall()
                
                indirectly_copied_products = cur.execute(
                    '''
                    SELECT DISTINCT p.id, p.event_id, p.name, p.price, p.image_id
                    FROM products AS p
                    LEFT JOIN product_booth_link AS bo_link ON bo_link.product_id = p.id
                    WHERE (p.event_id = ANY(%s)
                        OR bo_link.booth_id = ANY(%s))
                    ''',
                    (copied_events_ids, copied_booths_ids)).fetchall()
                
                copied_products = directly_copied_products + indirectly_copied_products
                
                for product in copied_products:
                    event_id = product['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                directly_copied_categories = cur.execute(
                    '''
                    SELECT id, name, event_id
                    FROM categories
                    WHERE id = ANY(%s)
                    ''',
                    (data_to_copy['category_ids'],)).fetchall()
                
                indirectly_copied_categories = cur.execute(
                    '''
                    SELECT DISTINCT c.id, c.name, c.event_id
                    FROM categories AS c
                    LEFT JOIN category_booth_link AS bo_link ON bo_link.category_id = c.id
                    WHERE (c.event_id = ANY(%s)
                        OR bo_link.booth_id = ANY(%s))
                    ''',
                    (copied_events_ids, copied_booths_ids)).fetchall()
                
                copied_categories = directly_copied_categories + indirectly_copied_categories

                for category in copied_categories:
                    event_id = category['event_id']
                    if event_id not in accessible_events_ids_for_logged_employee:
                        raise ForbiddenError()
                    
                # copied_directly -> přímo vybrané (id je v data_to_copy)
                # copied_indirectly -> kopírují se jen, protože se kopíruje něco, k čemu patří (booth, event)

                # copied_directly -> vždy se vytvoří jednou
                # copied_directly -> vytvoří se jednou, jen pokud se kopíruje z jiného eventu

                # copied_ids_already_created_per_target_event = { probably dont need this
                #     'copied_directly': {},
                #     'copied_indirectly': {}
                # }

                copied_to_created_ids_per_target_event = {
                    'copied_directly': {},
                    'copied_indirectly': {}
                }
                

                if target_events: # je zde, aby bylo jisté, že se kopíruje jen do event nebo jen do booth
                    manager_rows = []
                    booth_rows = []
                    product_rows = []
                    category_rows = []


                    # something copied as a child -> create it only if it doesnt exist or wasnt already created here
                    # something directly copied -> create it even it exists but dont if already created here


                    for target_event in target_events:
                        # for x in copied_ids_already_created_per_target_event:
                        #     if (x.get(target_event['id']) is None):
                        #         x[target_event['id']] = set()

                        copied_to_created_ids_per_target_event['copied_directly'][target_event['id']] = {}
                        copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']] = {}


                        if copied_managers:
                            # for manager in managers_to_copy:
                            #     cur.execute(
                            #         '''SELECT 1 FROM employee_event_booth_roles
                            #         WHERE employee_id = %s
                            #         AND event_id = %s''',
                            #         (manager['id'], target_event['id'])).fetchone()

                            manager_ids_of_target_event = cur.execute(
                                '''
                                SELECT employee_id
                                FROM employee_event_booth_roles
                                WHERE event_id = %s
                                AND booth_id IS NULL''',
                                (target_event['id'],))
                            
                            manager_ids_of_target_event = {manager['employee_id'] for manager in manager_ids_of_target_event}

                            if targets_are_new_events:
                                for manager in copied_managers:
                                    # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                    if manager['event_id'] != target_event['id_of_copied_event']:
                                        continue

                                    # if (manager['id'] in copied_ids_already_created_per_target_event['copied_directly'][target_event['id']]
                                    #     or manager['id'] in copied_ids_already_created_per_target_event['copied_indirectly'][target_event['id']]):
                                    #     continue

                                    # copied_ids_already_created_per_target_event['copied_directly'][target_event['id']].add(manager['id'])
                                    # copied_ids_already_created_per_target_event['copied_indirectly'][target_event['id']].add(manager['id'])

                                    manager_rows.append((
                                        manager['id'],
                                        target_event['id'],
                                        None
                                    ))

                                    copy_paste_row.employee_event_booth_roles_rows.append({
                                        'employee_id': manager['id'],
                                        'event_id': target_event['id'],
                                        'booth_id': None
                                    })
                            else:
                                # jestli se kopíruje stejný manager z různých events, tak ho zkopírujeme jen jednou
                                copied_managers_ids = {manager['id'] for manager in copied_managers}
                                for manager_id in copied_managers_ids:

                                    if manager_id in manager_ids_of_target_event:
                                        continue

                                    manager_rows.append({
                                        manager_id,
                                        target_event['id'],
                                        None
                                    })

                                    copy_paste_row.employee_event_booth_roles_rows.append({
                                        'employee_id': manager_id,
                                        'event_id': target_event['id'],
                                        'booth_id': None
                                    })
                        

                        if copied_booths:
                            lower_booth_names_of_target_event = cur.execute(
                            '''
                            SELECT name
                            FROM booths
                            WHERE event_id = %s
                            AND deleted_at IS NULL
                            ''',
                            (target_event['id'],)).fetchall()
                        
                            lower_booth_names_of_target_event = {booth['name'].lower() for booth in lower_booth_names_of_target_event}
                                
                            for booth in directly_copied_booths:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and booth['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if booth_to_copy['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(booth_to_copy['id'])

                                new_booth_name = make_unique_name(booth['name'], lower_booth_names_of_target_event)
                                lower_booth_names_of_target_event.add(new_booth_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_directly'][target_event['id']][booth['id']] = new_id

                                booth_rows.append((
                                    new_id,
                                    new_booth_name,
                                    target_event['id'],
                                    booth['booth_type'],
                                    logged_employee['id']
                                ))

                                copy_paste_row.booth_ids.append(new_id)

                            for booth in indirectly_copied_booths:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and booth['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if booth_to_copy['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(booth_to_copy['id'])

                                if booth['event_id'] == target_event['id']:
                                    copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][booth['id']] = booth['id']
                                    continue


                                new_booth_name = make_unique_name(booth['name'], lower_booth_names_of_target_event)
                                lower_booth_names_of_target_event.add(new_booth_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][booth['id']] = new_id

                                booth_rows.append((
                                    new_id,
                                    new_booth_name,
                                    target_event['id'],
                                    booth['booth_type'],
                                    logged_employee['id']
                                ))

                                copy_paste_row.booth_ids.append(new_id)


                        if copied_products:
                            lower_product_names_of_target_event = cur.execute(
                            '''
                            SELECT name
                            FROM products
                            WHERE event_id = %s
                            ''',
                            (target_event['id'],)).fetchall()

                            lower_product_names_of_target_event = {product['name'].lower() for product in lower_product_names_of_target_event}

                            for product in directly_copied_products:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and product['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if product['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(product['id'])

                                new_product_name = make_unique_name(product['name'], lower_product_names_of_target_event)
                                lower_product_names_of_target_event.add(new_product_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_directly'][target_event['id']][product['id']] = new_id

                                product_rows.append((
                                    new_id,
                                    target_event['id'],
                                    new_product_name,
                                    product['price'],
                                    product['image_id']
                                ))

                                copy_paste_row.product_ids.append(new_id)

                            for product in indirectly_copied_products:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and product['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if product['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(product['id'])

                                if product['event_id'] == target_event['id']:
                                    copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][product['id']] = product['id']
                                    continue

                                new_product_name = make_unique_name(product['name'], lower_product_names_of_target_event)
                                lower_product_names_of_target_event.add(new_product_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][product['id']] = new_id

                                product_rows.append((
                                    new_id,
                                    target_event['id'],
                                    new_product_name,
                                    product['price'],
                                    product['image_id']
                                ))

                                copy_paste_row.product_ids.append(new_id)


                        if copied_categories:
                            lower_category_names_of_target_event = cur.execute(
                            '''
                            SELECT name
                            FROM categories
                            WHERE event_id = %s
                            ''',
                            (target_event['id'],)).fetchall()

                            lower_category_names_of_target_event = {category['name'].lower() for category in lower_category_names_of_target_event}

                            for category in directly_copied_categories:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and category['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if category['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(category['id'])

                                new_category_name = make_unique_name(category['name'], lower_category_names_of_target_event)
                                lower_category_names_of_target_event.add(new_category_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_directly'][target_event['id']][category['id']] = new_id

                                category_rows.append((
                                    new_id,
                                    new_category_name,
                                    target_event['id']
                                ))

                                copy_paste_row.category_ids.append(new_id)

                            for category in indirectly_copied_categories:
                                # nové eventy -> zkopíruj data jen z jednoho původního eventu
                                if targets_are_new_events and category['event_id'] != target_event['id_of_copied_event']:
                                    continue

                                # if category['id'] in copied_ids_already_created_per_target_event[target_event['id']]:
                                #     continue
                                # copied_ids_already_created_per_target_event[target_event['id']].add(category['id'])

                                if category['event_id'] == target_event['id']:
                                    copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][category['id']] = category['id']
                                    continue

                                new_category_name = make_unique_name(category['name'], lower_category_names_of_target_event)
                                lower_category_names_of_target_event.add(new_category_name.lower())

                                new_id = uuid.uuid4()
                                copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][category['id']] = new_id

                                category_rows.append((
                                    new_id,
                                    new_category_name,
                                    target_event['id']
                                ))

                                copy_paste_row.category_ids.append(new_id)

                    
                    if manager_rows:
                        placeholders, params = get_placeholders_and_params(manager_rows)

                        # kontrola, že employee není admin nebo je deleted není potřeba, protože data se berou z této tabulky
                        cur.execute(
                            f'''
                            WITH input_data AS (
                            VALUES {placeholders}
                            ),
                            input_with_cols AS (
                            SELECT 
                                column1::uuid AS employee_id,
                                column2::uuid AS event_id,
                                column3::uuid AS booth_id
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
                            SELECT * FROM valid_rows''',
                            params)
                        
                    if booth_rows:
                        placeholders, params = get_placeholders_and_params(booth_rows)

                        cur.execute(
                            f'''
                            INSERT INTO booths
                            (id, name, event_id, booth_type, created_by)
                            VALUES {placeholders}
                            ''',
                            params)
                        
                    if product_rows:
                        placeholders, params = get_placeholders_and_params(product_rows)

                        cur.execute(
                            f'''
                            INSERT INTO products
                            (id, event_id, name, price, image_id)
                            VALUES {placeholders}
                            ''',
                            params)
                        
                    if category_rows:
                        placeholders, params = get_placeholders_and_params(category_rows)

                        cur.execute(
                            f'''
                            INSERT INTO categories
                            (id, name, event_id)
                            VALUES {placeholders}
                            ''',
                            params)


                    # vytovření řádků ve spojovacích tabulkách, kde to jde:

                    all_copied_ids = set()

                    for y in copied_to_created_ids_per_target_event.values():
                        # y je value pro copied_directly nebo copied_indirectly
                        for val in y.values():
                            # val je event_id: dict(old to new id)
                            all_copied_ids.update(val.keys())
                    all_copied_ids = list(all_copied_ids)

                    employee_event_booth_roles_rows = []
                    employee_booth_roles_to_copy = cur.execute(
                        '''
                        SELECT booth_id, employee_id, event_id
                        FROM employee_event_booth_roles
                        WHERE booth_id = ANY(%s)
                        ''',
                        (all_copied_ids,)).fetchall()
                    
                    product_booth_link_rows = []
                    product_booth_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.booth_id, link.product_id, bo.event_id
                        FROM product_booth_link AS link
                        JOIN booths AS bo ON bo.id = link.booth_id
                        WHERE link.booth_id = ANY(%s)
                        OR link.product_id = ANY(%s)
                        ''',
                        (all_copied_ids,
                         all_copied_ids)).fetchall()
                    
                    category_booth_link_rows = []
                    category_booth_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.booth_id, link.category_id, bo.event_id
                        FROM category_booth_link AS link
                        JOIN booths AS bo ON bo.id = link.booth_id
                        WHERE link.booth_id = ANY(%s)
                        OR link.category_id = ANY(%s)
                        ''',
                        (all_copied_ids,
                         all_copied_ids)).fetchall()
                    
                    category_product_link_rows = []
                    category_product_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.product_id, link.category_id, pr.event_id
                        FROM category_product_link AS link
                        JOIN products AS pr ON pr.id = link.product_id
                        WHERE link.product_id = ANY(%s)
                        OR link.category_id = ANY(%s)
                        ''',
                        (all_copied_ids,
                         all_copied_ids)).fetchall()


                    for target_event in target_events:
                        # booths x employees
                        for row in employee_booth_roles_to_copy:
                            # if targets_are_new_events and row['event_id'] != target_event['id_of_copied_event']:
                            #     continue

                            for value in copied_to_created_ids_per_target_event.values():
                                # udělej to stejné pro directly a indirectly
                                new_booth_id = value[target_event['id']].get(row['booth_id'])

                                if new_booth_id and new_booth_id != row['booth_id']:
                                    employee_event_booth_roles_rows.append((
                                        new_booth_id,
                                        row['employee_id'],
                                        target_event['id']
                                    ))

                                    copy_paste_row.employee_event_booth_roles_rows.append({
                                        'booth_id': new_booth_id,
                                        'employee_id': row['employee_id'],
                                        'event_id': target_event['id']
                                    })

                            
                        # booths x products
                        for row in product_booth_links_to_copy:

                            for value in copied_to_created_ids_per_target_event.values():
                                new_booth_id = value[target_event['id']].get(row['booth_id'])

                                if new_booth_id and new_booth_id != row['booth_id']:
                                    new_product_id = copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][row['product_id']]

                                    product_booth_link_rows.append((
                                    new_booth_id,
                                    new_product_id
                                    ))

                                    copy_paste_row.product_booth_link_rows.append({
                                        'booth_id': new_booth_id,
                                        'product_id': new_product_id
                                    })

                            if target_event['id'] == row['event_id']:
                                new_product_id = copied_to_created_ids_per_target_event['copied_directly'][target_event['id']].get(row['product_id'])

                                if new_product_id:
                                    product_booth_link_rows.append((
                                    row['booth_id'],
                                    new_product_id
                                    ))

                                    copy_paste_row.product_booth_link_rows.append({
                                        'booth_id': row['booth_id'],
                                        'product_id': new_product_id
                                    })

                            
                        # booths x categories
                        for row in category_booth_links_to_copy:

                            for value in copied_to_created_ids_per_target_event.values():
                                new_booth_id = value[target_event['id']].get(row['booth_id'])

                                if new_booth_id and new_booth_id != row['booth_id']:
                                    new_category_id = copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']][row['category_id']]

                                    category_booth_link_rows.append((
                                    new_booth_id,
                                    new_category_id
                                    ))

                                    copy_paste_row.category_booth_link_rows.append({
                                        'booth_id': new_booth_id,
                                        'category_id': new_category_id
                                    })


                            if target_event['id'] == row['event_id']:
                                new_category_id = copied_to_created_ids_per_target_event['copied_directly'][target_event['id']].get(row['category_id'])

                                if new_category_id:
                                    category_booth_link_rows.append((
                                    row['booth_id'],
                                    new_category_id
                                    ))

                                    copy_paste_row.category_booth_link_rows.append({
                                        'booth_id': row['booth_id'],
                                        'category_id': new_category_id
                                    })
                            
                        # products x categories
                        for row in category_product_links_to_copy:
                            new_product_id = copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']].get(row['product_id'])
                            new_category_id = copied_to_created_ids_per_target_event['copied_indirectly'][target_event['id']].get(row['category_id'])

                            if new_product_id and new_category_id and (new_product_id != row['product_id'] or new_category_id != row['category_id']):
                                category_product_link_rows.append((
                                new_product_id,
                                new_category_id
                                ))

                                copy_paste_row.category_product_link_rows.append({
                                    'product_id': new_product_id,
                                    'category_id': new_category_id
                                })


                            if target_event['id'] == row['event_id']:
                                new_product_id = copied_to_created_ids_per_target_event['copied_directly'][target_event['id']].get(row['product_id'])

                                if new_product_id:
                                    category_product_link_rows.append((
                                    new_product_id,
                                    row['category_id']
                                    ))

                                    copy_paste_row.category_product_link_rows.append({
                                        'product_id': new_product_id,
                                        'category_id': row['category_id']
                                    })

                                new_category_id = copied_to_created_ids_per_target_event['copied_directly'][target_event['id']].get(row['category_id'])

                                if new_category_id:
                                    category_product_link_rows.append((
                                    row['product_id'],
                                    new_category_id
                                    ))

                                    copy_paste_row.category_product_link_rows.append({
                                        'product_id': row['product_id'],
                                        'category_id': new_category_id
                                    })

                            
                    if employee_event_booth_roles_rows:
                        placeholders, params = get_placeholders_and_params(employee_event_booth_roles_rows)
                        cur.execute(
                            f'''
                            WITH input_data AS (
                            VALUES {placeholders}
                            ),
                            input_with_cols AS (
                            SELECT 
                                column1::uuid AS booth_id,
                                column2::uuid AS employee_id,
                                column3::uuid AS event_id
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
                                    AND link.booth_id IS NULL -- already a manager
                                )
                            )
                            INSERT INTO employee_event_booth_roles (booth_id, employee_id, event_id)
                            SELECT booth_id, employee_id, event_id FROM valid_rows
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    if product_booth_link_rows:
                        placeholders, params = get_placeholders_and_params(product_booth_link_rows)

                        cur.execute(
                            f'''
                            INSERT INTO product_booth_link
                            (booth_id, product_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    if category_booth_link_rows:
                        placeholders, params = get_placeholders_and_params(category_booth_link_rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_booth_link
                            (booth_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                        
                    if category_product_link_rows:
                        placeholders, params = get_placeholders_and_params(category_product_link_rows)

                        cur.execute(
                            f'''
                            INSERT INTO category_product_link
                            (product_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)



                elif target_booths:
                    target_booths_by_event = {}
                    for booth in target_booths:
                        event_id = booth['event_id']
                        if event_id not in target_booths_by_event:
                            target_booths_by_event[event_id] = []
                        target_booths_by_event[event_id].append(booth)

                    created_ids_per_event = {}

                    product_rows = []
                    category_rows = []

                    for event_id, event_target_booths in target_booths_by_event.items():
                        created_ids_per_event[event_id] = {
                            'products': {},
                            'categories': {}
                        }
                        
                        # Vytvoř products a categories, které v tomto event neexistují
                        for product in copied_products:
                            if product['event_id'] == event_id:
                                created_ids_per_event[event_id]['products'][product['id']] = product['id']
                                continue

                            if product['id'] in created_ids_per_event[event_id]['products']:
                                continue


                            new_id = uuid.uuid4()
                            created_ids_per_event[event_id]['products'][product['id']] = new_id
                            
                            product_rows.append((
                                new_id,
                                event_id,
                                product['name'],
                                product['price'],
                                product['image_id']
                            ))
                            
                            copy_paste_row.product_ids.append(new_id)
                        

                        for category in copied_categories:

                            if category['event_id'] == event_id:
                                created_ids_per_event[event_id]['categories'][category['id']] = category['id']
                                continue

                            if category['id'] in created_ids_per_event[event_id]['categories']:
                                continue


                            new_id = uuid.uuid4()
                            created_ids_per_event[event_id]['categories'][category['id']] = new_id
                            
                            category_rows.append((
                                new_id,
                                category['name'],
                                event_id
                            ))
                            
                            copy_paste_row.category_ids.append(new_id)


                    if product_rows:
                        placeholders, params = get_placeholders_and_params(product_rows)
                        cur.execute(
                            f'''
                            INSERT INTO products
                            (id, event_id, name, price, image_id)
                            VALUES {placeholders}
                            ''',
                            params)
                        
                    if category_rows:
                        placeholders, params = get_placeholders_and_params(category_rows)
                        cur.execute(
                            f'''
                            INSERT INTO categories
                            (id, name, event_id)
                            VALUES {placeholders}
                            ''',
                            params)
                    

                    all_copied_ids = set()
                    all_copied_ids.update(copied_booths_ids)
                    all_copied_ids.update(product['id'] for product in copied_products)
                    all_copied_ids.update(category['id'] for category in copied_categories)
                    all_copied_ids = list(all_copied_ids)
                    
                    # Fetch linking rows from database
                    employee_event_booth_roles_rows = []
                    employee_booth_roles_to_copy = cur.execute(
                        '''
                        SELECT booth_id, employee_id, event_id
                        FROM employee_event_booth_roles
                        WHERE booth_id = ANY(%s)
                        OR employee_id = ANY(%s)
                        ''',
                        (all_copied_ids, data_to_copy['employees_to_assign_to_target_booths'])).fetchall()
                    
                    employee_ids_assigned_per_target_booth = cur.execute(
                        '''
                        SELECT booth_id, employee_id
                        FROM employee_event_booth_roles
                        WHERE booth_id = ANY(%s)
                        ''',
                        ([booth['id'] for booth in target_booths],)).fetchall()
                    
                    employee_ids_assigned_per_target_booth = {row['employee_id'] for row in employee_ids_assigned_per_target_booth}
                    
                    product_booth_link_rows = []
                    product_booth_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.booth_id, link.product_id, bo.event_id
                        FROM product_booth_link AS link
                        JOIN booths AS bo ON bo.id = link.booth_id
                        WHERE link.booth_id = ANY(%s)
                        OR link.product_id = ANY(%s)
                        ''',
                        (all_copied_ids, all_copied_ids)).fetchall()
                    
                    category_booth_link_rows = []
                    category_booth_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.booth_id, link.category_id, bo.event_id
                        FROM category_booth_link AS link
                        JOIN booths AS bo ON bo.id = link.booth_id
                        WHERE link.booth_id = ANY(%s)
                        OR link.category_id = ANY(%s)
                        ''',
                        (all_copied_ids, all_copied_ids)).fetchall()
                    
                    category_product_link_rows = []
                    category_product_links_to_copy = cur.execute(
                        '''
                        SELECT DISTINCT link.product_id, link.category_id, pr.event_id
                        FROM category_product_link AS link
                        JOIN products AS pr ON pr.id = link.product_id
                        WHERE link.product_id = ANY(%s)
                        OR link.category_id = ANY(%s)
                        ''',
                        (all_copied_ids, all_copied_ids)).fetchall()
                    

                    for booth in target_booths:
                        # employees x booths
                        for row in employee_booth_roles_to_copy:
                            if row['booth_id'] == booth['id'] and row['employee_id'] in employee_ids_assigned_per_target_booth:
                                continue

                            employee_event_booth_roles_rows.append((
                                booth['id'],
                                row['employee_id'],
                                booth['event_id']
                            ))
                            
                            copy_paste_row.employee_event_booth_roles_rows.append({
                                'booth_id': booth['id'],
                                'employee_id': row['employee_id'],
                                'event_id': booth['event_id']
                            })
                        
                        if booth['booth_type'] == 'seller':
                            # products x booths
                            for row in product_booth_links_to_copy:
                                new_product_id = created_ids_per_event[booth['event_id']]['products'].get(row['product_id'])

                                if row['booth_id'] == booth['id'] and row['product_id'] == new_product_id:
                                    continue
                                    
                                if new_product_id:
                                    product_booth_link_rows.append((
                                        booth['id'],
                                        new_product_id
                                    ))
                                    
                                    copy_paste_row.product_booth_link_rows.append({
                                        'booth_id': booth['id'],
                                        'product_id': new_product_id
                                    })
                        
                        if booth['booth_type'] == 'seller':
                            # categories x booths
                            for row in category_booth_links_to_copy:
                                new_category_id = created_ids_per_event[booth['event_id']]['categories'].get(row['category_id'])

                                if row['booth_id'] == booth['id'] and row['category_id'] == new_category_id:
                                    continue

                                if new_category_id:
                                    category_booth_link_rows.append((
                                        booth['id'],
                                        new_category_id
                                    ))
                                    
                                    copy_paste_row.category_booth_link_rows.append({
                                        'booth_id': booth['id'],
                                        'category_id': new_category_id
                                    })
                        
                        # products x categories
                        for row in category_product_links_to_copy:
                            new_product_id = created_ids_per_event[booth['event_id']]['products'].get(row['product_id'])
                            new_category_id = created_ids_per_event[booth['event_id']]['categories'].get(row['category_id'])

                            if row['product_id'] == new_product_id and row['category_id'] == new_category_id:
                                continue

                            if (new_product_id and new_category_id):
                                category_product_link_rows.append((
                                    new_product_id,
                                    new_category_id
                                ))
                                
                                copy_paste_row.category_product_link_rows.append({
                                    'product_id': new_product_id,
                                    'category_id': new_category_id
                                })
                    

                    if employee_event_booth_roles_rows:
                        placeholders, params = get_placeholders_and_params(employee_event_booth_roles_rows)
                        cur.execute(
                            f'''
                            WITH input_data AS (
                            VALUES {placeholders}
                            ),
                            input_with_cols AS (
                            SELECT 
                                column1::uuid AS booth_id,
                                column2::uuid AS employee_id,
                                column3::uuid AS event_id
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
                            ON CONFLICT DO NOTHING''',
                            params)
                    
                    if product_booth_link_rows:
                        placeholders, params = get_placeholders_and_params(product_booth_link_rows)
                        cur.execute(
                            f'''
                            INSERT INTO product_booth_link
                            (booth_id, product_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                    
                    if category_booth_link_rows:
                        placeholders, params = get_placeholders_and_params(category_booth_link_rows)
                        cur.execute(
                            f'''
                            INSERT INTO category_booth_link
                            (booth_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)
                    
                    if category_product_link_rows:
                        placeholders, params = get_placeholders_and_params(category_product_link_rows)
                        cur.execute(
                            f'''
                            INSERT INTO category_product_link
                            (product_id, category_id)
                            VALUES {placeholders}
                            ON CONFLICT DO NOTHING''',
                            params)


                save_copy_paste(copy_paste_row)

    except ForbiddenError:
        return jsonify(error='insufficient_priviliges'), 403
    except CanNotMakeNewEventIfNotCopyingEvent:
        return jsonify(error='can_not_make_new_event_if_not_copying_event'), 400

    return jsonify(), 200


api_bp = Blueprint('paste_api', __name__, url_prefix='/api/paste')


@api_bp.route('', methods=('POST',))
def paste():
    # if target is new events, then i need to make the items only from one event every time

    logged_employee = load_logged_in_employee() ######## do more validation

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    if not request.is_json:
        return jsonify(error='invalid_mimetype'), 400

    data : dict | None = request.get_json(silent=True)

    if data is None:
        return jsonify(error='invalid_request_body'), 400
    
    frontend_targets = data.get('targets') # to event, new event, a booth (cant copy to employees)

    if not frontend_targets:
        return jsonify(error='missing_targets'), 400
    
    if frontend_targets in ['newEvents', 'newEmployees'] and not logged_employee['is_admin']:
        return jsonify(error='insufficient_priviliges'), 403

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
    
    # isnt necessary?:
    # if (not frontend_data_to_copy['eventIds']
    #     and not frontend_data_to_copy['boothIds']
    #     and not frontend_data_to_copy['productIds']
    #     and not frontend_data_to_copy['categoryIds']
    #     and not frontend_data_to_copy['managerIds']
    #     and not frontend_data_to_copy['employeeIds']):
    #     return jsonify(error='no_data_to_copy'), 400

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


@api_bp.route('/undo', methods=('POST',))
def undo_paste():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                last_valid_paste = cur.execute(
                    '''
                    SELECT paste.*
                    FROM copy_paste_history AS paste
                    LEFT JOIN undo_copy_paste as undo ON undo.copy_paste_history_id = paste.id
                    WHERE paste.performed_by = %s
                    AND undo.id IS NULL
                    ORDER BY paste.occurred_at DESC
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)).fetchone()

                if not last_valid_paste:
                    raise NoPasteToUndo()

                last_valid_paste = CopyPasteRow(**last_valid_paste)
                

                if last_valid_paste.employee_ids:
                    cur.execute(
                        '''
                        UPDATE employees
                        SET deleted_at = now()
                        WHERE id = ANY(%s)
                        AND deleted_at IS NULL
                        ''',
                        (last_valid_paste.employee_ids,))


                if last_valid_paste.event_ids:
                    cur.execute(
                        '''
                        UPDATE events
                        SET deleted_at = now()
                        WHERE id = ANY(%s)
                        AND deleted_at IS NULL
                        ''',
                        (last_valid_paste.event_ids,))
                
                if last_valid_paste.booth_ids:
                    cur.execute(
                        '''
                        UPDATE booths
                        SET deleted_at = now()
                        WHERE id = ANY(%s)
                        AND deleted_at IS NULL
                        ''',
                        (last_valid_paste.booth_ids,))
                    
                if last_valid_paste.product_ids:
                    cur.execute(
                        '''
                        DELETE FROM products
                        WHERE id = ANY(%s)
                        ''',
                        (last_valid_paste.product_ids,))
                    
                if last_valid_paste.category_ids:
                    cur.execute(
                        '''
                        DELETE FROM categories
                        WHERE id = ANY(%s)
                        ''',
                        (last_valid_paste.category_ids,))
                    

                rows = last_valid_paste.employee_event_booth_roles_rows
                # booth_id může být null, proto se to liší od ostatních
                if rows:
                    cols = ['booth_id', 'event_id', 'employee_id']

                    col_type = {
                        'booth_id': 'uuid',
                        'event_id': 'uuid',
                        'employee_id': 'uuid',
                    }

                    # "(%s::uuid, %s::uuid, %s::uuid)"
                    per_row_placeholder = '(' + ', '.join('%s::' + col_type[c] for c in cols) + ')'

                    placeholders = ', '.join(per_row_placeholder for _ in rows)

                    params = []
                    for row in rows:
                        for c in cols:
                            params.append(row.get(c))

                    cur.execute(
                        f"""
                        WITH to_delete ({', '.join(cols)}) AS (
                            VALUES {placeholders}
                        )
                        DELETE FROM employee_event_booth_roles e
                        USING to_delete t
                        WHERE e.event_id = t.event_id
                        AND e.employee_id = t.employee_id
                        AND (e.booth_id IS NOT DISTINCT FROM t.booth_id)
                        """,
                        params
                    )
                    
                if last_valid_paste.product_booth_link_rows:
                    columns, placeholders, params = get_delete_columns_placeholders_and_params(last_valid_paste.product_booth_link_rows)

                    cur.execute(
                        f'''
                        DELETE FROM product_booth_link 
                        WHERE {columns} IN (VALUES {placeholders})
                        ''',
                        params)
                    
                if last_valid_paste.category_booth_link_rows:
                    columns, placeholders, params = get_delete_columns_placeholders_and_params(last_valid_paste.category_booth_link_rows)

                    cur.execute(
                        f'''
                        DELETE FROM category_booth_link 
                        WHERE {columns} IN (VALUES {placeholders})
                        ''',
                        params)

                if last_valid_paste.category_product_link_rows:
                    columns, placeholders, params = get_delete_columns_placeholders_and_params(last_valid_paste.category_product_link_rows)

                    cur.execute(
                        f'''
                        DELETE FROM category_product_link 
                        WHERE {columns} IN (VALUES {placeholders})
                        ''',
                        params)


                cur.execute(
                    '''
                    INSERT INTO undo_copy_paste
                    (copy_paste_history_id)
                    VALUES (%s)
                    ''',
                    (last_valid_paste.id,))

    except NoPasteToUndo:
        return jsonify(message='no_paste_to_undo'), 200

    return jsonify(), 200


@api_bp.route('/redo', methods=('POST',))
def redo_paste():
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                last_valid_undo_paste_dict = cur.execute(
                    '''
                    SELECT paste.*, undo.id AS undo_id
                    FROM undo_copy_paste AS undo
                    JOIN copy_paste_history AS paste ON paste.id = undo.copy_paste_history_id
                    WHERE paste.performed_by = %s
                    AND undo.was_redone IS FALSE
                    ORDER BY undo.occurred_at DESC
                    LIMIT 1
                    ''',
                    (logged_employee['id'],)).fetchone()

                if not last_valid_undo_paste_dict:
                    raise NoPasteToRedo()
                
                undo_id = last_valid_undo_paste_dict.pop('undo_id')
                
                last_valid_undo_paste = CopyPasteRow(**last_valid_undo_paste_dict)

                target_ids = {
                    'event_ids': last_valid_undo_paste.target_event_ids,
                    'booth_ids': last_valid_undo_paste.target_booth_ids
                }

                cur.execute(
                    '''
                    UPDATE undo_copy_paste
                    SET was_redone = TRUE
                    WHERE id = %s
                    ''',
                    (undo_id,))

                return do_paste(
                    last_valid_undo_paste.data_to_copy,
                    target_ids,
                    last_valid_undo_paste.targets_were_new_employees,
                    last_valid_undo_paste.targets_were_new_events,
                    logged_employee)

    except NoPasteToRedo:
        return jsonify(message='no_paste_to_redo'), 200
