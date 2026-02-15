from uuid import UUID
from typing import Any
import hashlib
from psycopg import IntegrityError
from flask import request

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


def get_employee_lock_key(employee_id: UUID, namespace: str | int = 1001) -> int:
    """
    Convert employee UUID + namespace to a consistent signed 64-bit int suitable for
    an advisory lock key.

    - `namespace` may be an int or a str (default 1001).
    - Different namespace values produce different keys for the same UUID.
    """
    namespace = str(namespace)
    input_bytes = (f"{namespace}:{employee_id}").encode("utf-8")
    hash_bytes = hashlib.md5(input_bytes).digest()
    # vezmi prvních 8 bytes jako signed 64-bit int
    key = int.from_bytes(hash_bytes[:8], "big", signed=True)
    return key


def client_ip_from_request() -> str:
    """Získej klientskou IP adresu z požadavku.


    Nejprve se pokusí použít hlavičku X-Forwarded-For (první IP v seznamu),
    pokud není nastavena, použije `request.remote_addr`.
    
    
    POZOR: pokud přijímáte požadavky přes reverzní proxy, je nezbytné
    zajistit, aby proxy správně předávala tuto hlavičku a aby jí bylo důvěřováno.
    """
    ######
    # If you are behind a reverse proxy, ensure that Flask/your proxy
    # is configured to pass the correct header and that you trust it.
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        # take the first IP in X-Forwarded-For (the originating IP)
        ips = [p.strip() for p in xff.split(',') if p.strip()]
        if ips:
            return ips[0]
    # fallback to remote_addr
    return request.remote_addr or ''


def get_constraint_name(integrity_error: IntegrityError):
    constraint = None
    try:
        constraint = getattr(integrity_error, 'diag', None) and integrity_error.diag.constraint_name
    except Exception:
        constraint = None

    return constraint