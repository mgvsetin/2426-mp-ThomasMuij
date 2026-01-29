import json
import hashlib
from flask import jsonify
from psycopg.types.json import Jsonb
from psycopg.errors import RaiseException
from psycopg import Cursor
from cashier_app.errors import InsufficientBalanceError, IdempotencyKeyDataConflict, UnexpectedError
from cashier_app.utils.general import convert_uuids_to_str
from cashier_app.db import get_pool


def make_transaction(params: dict, cursor: Cursor | None = None):
    # params = {
    # 'tag_id': tag_id,
    # 'wallet_id': wallet['id'],
    # 'user_id': wallet['owner_id'],
    # 'event_id': event['id'],
    # 'booth_id': booth['id'],
    # 'transaction_type': 'payment',
    # 'amount_czk': amount_czk,
    # 'performed_by': logged_employee['id'],
    # 'products_info': Jsonb(products_info),
    # 'idempotency_key': idemp_key
    # }

    idemp_key = params['idempotency_key']

    fingerprint_cols = dict(params)

    fingerprint_source = json.dumps(
        {key: convert_uuids_to_str(value) for key, value in fingerprint_cols.items()},
        separators=(',', ':'), sort_keys=True)
    request_fingerprint = hashlib.sha256(fingerprint_source.encode('utf-8')).hexdigest()

    params = dict(params)
    params['products_info'] = Jsonb(params['products_info'])
    params['request_fingerprint'] = request_fingerprint


    def handle_insert(cur: Cursor):
        cols_str = ', '.join(params.keys())
        col_values_placeholders = ', '.join([f'%({col})s' for col in params.keys()])

        cur.execute(
            f'''
            INSERT INTO transactions
            ({cols_str})
            VALUES ({col_values_placeholders})
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            ''',
            params)
        # wallet se updatuje pomocí trigger v db
        inserted = cur.fetchone()

        if not inserted:                
            cur.execute(
                '''
                SELECT id, request_fingerprint
                FROM transactions
                WHERE idempotency_key = %s
                ''', (idemp_key,))
            existing = cur.fetchone()

            if not existing:
                raise UnexpectedError()
            
            existing_fingerprint = existing['request_fingerprint']

            if existing_fingerprint != params['request_fingerprint']:
                raise IdempotencyKeyDataConflict()
    
    try:
        if cursor:
            handle_insert(cursor)
        else:
            with get_pool().connection() as conn:
                with conn.cursor() as cursor:
                    handle_insert(cursor)
    except RaiseException as e:
        text = str(e)

        if "insufficient balance" in text:
            raise InsufficientBalanceError()
        else:
            raise UnexpectedError()