"""Server-side session backend pro Flask s úložištěm v PostgreSQL.

Modul poskytuje:
- PgSession -- objekt relace odvozený od CallbackDict a SessionMixin,
  který automaticky detekuje změny dat.
- PgSessionInterface -- vlastní implementaci rozhraní SessionInterface,
  jež čte a zapisuje data relací do zadané tabulky (výchozí ``sessions``)
  ve formátu JSONB.
- Pomocné utility: zkrácený hash User-Agent řetězce, mazání
  expirovaných relací a CLI příkaz pro údržbu databáze.
"""

from typing import Callable, Optional, Dict, Any
from psycopg_pool import ConnectionPool
import json
import secrets
import datetime
import hashlib
from flask import Flask
from flask.sessions import SessionInterface, SessionMixin
from flask.wrappers import Request, Response
from werkzeug.datastructures import CallbackDict
from psycopg import sql
from psycopg.types.json import Json
from flask import request

from cashier_app.utils.general import client_ip_from_request
from cashier_app.utils.query_builder import build_delete_statement

from cashier_app.db import get_pool


class PgSession(CallbackDict, SessionMixin):
    """Objekt relace ukládaný na straně serveru v PostgreSQL.

    Dědí z ``CallbackDict``, takže každá změna klíče automaticky nastaví
    příznak ``modified`` na ``True``.  Zároveň implementuje ``SessionMixin``,
    čímž je plně kompatibilní s Flask session API.
    """
    def __init__(self, initial: Optional[Dict[str, Any]] = None, sid: Optional[str] = None, new: bool = False) -> None:
        """Inicializuje objekt relace.

        Parametry
        ---------
        initial : dict | None
            Počáteční data relace (načtená z databáze nebo prázdná).
        sid : str | None
            Identifikátor relace uložený v cookie prohlížeče.
        new : bool
            ``True``, pokud se jedná o zcela novou relaci.
        """
        def _on_update(self):
            self.modified = True
        super().__init__(initial or {}, _on_update)
        self.sid = sid
        self.new = new
        self.modified = False


def short_ua_hash(user_agent: str) -> str:
    """Vrátí prvních 16 hexadecimálních znaků SHA-256 hashe řetězce User-Agent.

    Slouží k rychlé detekci změny prohlížeče mezi požadavky, aniž by se
    do databáze ukládal celý řetězec User-Agent.
    """
    # vrátí prvních 16 hex znaků sha256
    if not user_agent:
        return ''
    return hashlib.sha256(user_agent.encode('utf-8')).hexdigest()[:16]


class PgSessionInterface(SessionInterface):
    """Rozhraní pro správu relací s úložištěm v PostgreSQL.

    Implementuje metody ``open_session`` (načtení relace z databáze podle
    SID uloženého v cookie) a ``save_session`` (uložení / aktualizace relace
    v databázi a nastavení cookie v HTTP odpovědi).

    Parametry
    ---------
    get_db_pool : callable
        Funkce vracející instanci ``ConnectionPool`` (výchozí ``get_pool``).
    table : str
        Název databázové tabulky pro ukládání relací (výchozí ``'sessions'``).
    """
    serializer = json
    session_class = PgSession

    def __init__(self, get_db_pool: Callable[[], "ConnectionPool"] = get_pool, table: str = 'sessions') -> None:
        self.get_pool = get_db_pool
        self.table = table

    def generate_sid(self) -> str:
        """Vygeneruje kryptograficky bezpečný identifikátor relace.

        Využívá ``secrets.token_urlsafe(32)`` pro dostatečnou entropii,
        výsledek se použije jako hodnota cookie.
        """
        return secrets.token_urlsafe(32)

    def get_expiration_time(self, app: Flask, session: SessionMixin) -> Optional[datetime.datetime]:
        """Vypočítá čas vypršení platnosti relace.

        Je-li relace označena jako ``permanent``, vrátí aktuální UTC čas
        posunutý o ``app.permanent_session_lifetime``.  V opačném případě
        vrátí ``None`` -- cookie pak platí jen do zavření prohlížeče.
        """
        if session.permanent:
            return datetime.datetime.now(datetime.timezone.utc) + app.permanent_session_lifetime
        return None
    
    def open_session(self, app: Flask, request: Request) -> PgSession:
        """Načte relaci z databáze podle SID uloženého v cookie.

        Ověřuje platnost expirace a volitelně kontroluje shodu User-Agent
        (``SESSION_ENFORCE_UA``) a IP adresy (``SESSION_ENFORCE_IP``).
        Pokud relace neexistuje, vypršela nebo neprošla validací, vrátí
        novou prázdnou relaci.
        """
        sid = request.cookies.get(app.config.get("SESSION_COOKIE_NAME", "session"))
        if not sid:
            return self.session_class(sid=None, new=True)

        with self.get_pool().connection() as conn:
            with conn.cursor() as cur:
                row = cur.execute(
                    sql.SQL('''
                    SELECT data, employee_id, ip, ua_hash, expires_at
                    FROM {table}
                    WHERE id = %s''').format(
                        table=sql.Identifier(self.table)
                    ),
                    (sid,)).fetchone()
                if not row:
                    return self.session_class(sid=None, new=True)
                
                if row['expires_at'] is not None and row['expires_at'] < datetime.datetime.now(datetime.timezone.utc):
                    # vypršela platnost
                    query, query_params = build_delete_statement(self.table, sid, soft_delete=False)
                    cur.execute(query, query_params)

                    return self.session_class(sid=None, new=True)
                
                enforce_ua = app.config.get('SESSION_ENFORCE_UA', False)
                if enforce_ua:
                    actual_ua_hash = short_ua_hash(request.headers.get('User-Agent', ''))
                    if row['ua_hash'] and row['ua_hash'] != actual_ua_hash:
                        # neshoda UA -> zneplatnění relace
                        query, query_params = build_delete_statement(self.table, sid, soft_delete=False)
                        cur.execute(query, query_params)
                        return self.session_class(sid=None, new=True)
                    
                enforce_ip = app.config.get('SESSION_ENFORCE_IP', False)
                if enforce_ip:
                    actual_ip = client_ip_from_request()
                    if row['ip'] and row['ip'] != actual_ip:
                        # neshoda IP -> zneplatnění relace
                        query, query_params = build_delete_statement(self.table, sid, soft_delete=False)
                        cur.execute(query, query_params)
                        return self.session_class(sid=None, new=True)
                
        data = row['data'] or {}
        return self.session_class(initial=data, sid=sid, new=False)
    
    def save_session(self, app: Flask, session: PgSession, response: Response) -> None:
        """Uloží relaci do databáze a nastaví cookie v HTTP odpovědi.

        Prázdná relace je z databáze odstraněna a cookie smazána.
        Při nové relaci nebo explicitní regeneraci SID se vygeneruje nový
        identifikátor a starý záznam (pokud existoval) se odstraní.
        """
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        # je zde, aby se regenerate vždy odstranilo
        regenerate = session.pop('_regenerate', False)

        # prázdná relace -> smazat cookie i záznam v DB
        if not session:
            if session.sid:
                with self.get_pool().connection() as conn:
                    with conn.cursor() as cur:
                        query, query_params = build_delete_statement(self.table, session.sid, soft_delete=False)
                        cur.execute(query, query_params)

            response.delete_cookie(
                app.config.get("SESSION_COOKIE_NAME", "session"),
                domain=domain,
                path=path
            )
            return
        
        if not session.modified and not session.new and not regenerate:
            return
        
        # Nové SID při nové relaci nebo explicitní regeneraci
        sid = session.sid
        if session.new or not sid or regenerate:
            new_sid = self.generate_sid()
        else:
            new_sid = sid

        expires = self.get_expiration_time(app, session)
        data = dict(session) # pouze JSON serializovatelné položky

        # metadata: employee_id (pokud existuje), ua_hash, ip
        employee_id = data.get('employee_id')
        ua_hash = short_ua_hash(request.headers.get('User-Agent', ''))
        ip = client_ip_from_request()

        with self.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("""
                    INSERT INTO {table} (id, data, employee_id, ip, ua_hash, modified_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, now(), %s)
                    ON CONFLICT (id) DO UPDATE
                    SET data = EXCLUDED.data,
                    employee_id = EXCLUDED.employee_id,
                    ip = EXCLUDED.ip,
                    ua_hash = EXCLUDED.ua_hash,
                    modified_at = now(),
                    expires_at = EXCLUDED.expires_at
                    """).format(
                        table=sql.Identifier(self.table)
                    ),
                    (new_sid, Json(data), employee_id, ip, ua_hash, expires))

                if (new_sid != sid) and sid:
                    try:
                        query, query_params = build_delete_statement(self.table, sid, soft_delete=False)
                        cur.execute(query, query_params)
                    except Exception:
                        # Chyba při mazání starého SID není fatální
                        pass

        session.sid = new_sid
        session.new = False
                
        # nastavení cookie (hodnota cookie je neprůhledné SID)
        response.set_cookie(
            app.config.get("SESSION_COOKIE_NAME", "session"),
            new_sid,
            expires=expires,
            httponly=app.config.get('SESSION_COOKIE_HTTPONLY', True),
            samesite=app.config.get('SESSION_COOKIE_SAMESITE', 'Lax'),
            secure=app.config.get('SESSION_COOKIE_SECURE', False),
            domain=domain,
            path=path
        )


# --- Mazání expirovaných relací (volatelné z CLI/cronu) ---
def delete_expired_sessions(max_inactive_days: int | None = None) -> int:
    """Smaže z DB expirované sessiony a (volitelně) staré řádky bez expires_at.


    Parametry
    ---------
    max_inactive_days: int | None
    Pokud je zadáno, smaže i řádky kde expires_at IS NULL a upraveno bylo
    více než `max_inactive_days` dní.
    
    
    Vrací
    -----
    int
    Počet smazaných řádků.
    """
    if max_inactive_days is None:
        try:
            from flask import current_app, has_app_context
            if has_app_context():
                max_inactive_days = current_app.config.get('SESSION_MAX_INACTIVE_DAYS', None)
        except Exception:
            pass

    deleted = 0

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM sessions
                WHERE expires_at IS NOT NULL AND expires_at < now()
                RETURNING id;
                """)
            deleted += len(cur.fetchall())

            if max_inactive_days is not None:
                days = int(max_inactive_days)
                cur.execute(
                    """
                    DELETE FROM sessions
                    WHERE expires_at IS NULL
                      AND modified_at < now() - make_interval(days => %s)
                    RETURNING id;
                    """,
                    (days,))
                deleted += len(cur.fetchall())

    return deleted

import click
from flask import current_app

@click.command('clear-sessions')
def clear_sessions_command():
    """Smaže expirované relace z databáze."""
    deleted = delete_expired_sessions()
    click.echo(f"Deleted {deleted} expired sessions.")
