"""Implementace session backendu ukládajícího sessiony do PostgreSQL.


Tento modul definuje:
- PgSession: objekt session kompatibilní s Flask-Sessions (SessionMixin).
- PgSessionInterface: vlastní SessionInterface pro Flask, který ukládá
session data do tabulky (defaultně `sessions`) jako jsonb.
- Pomocné funkce pro zkrácení UA (hash), extrakci klientského IP a nástroje
pro čištění/odstranění expirovaných session z databáze.
"""

import json
import secrets
import datetime
import hashlib
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict
from psycopg.types.json import Json
from flask import current_app, request, session as flask_session

from cashier_app.db import get_pool

# 1) Sliding vs fixed expiry

# The example uses session.permanent + app.permanent_session_lifetime. 
# If you want sliding expiry (extend expires_at on activity), 
# update modified_at and set expires_at to now() + lifetime on each 
# save_session (we already set expires_at to computed value, 
# you can choose to set it to datetime.utcnow() + lifetime 
# on each save to slide).


# 3) Revoking all user sessions

# Because we have employee_id column, you can revoke all sessions for an employee quickly:

# DELETE FROM sessions WHERE employee_id = '...';


# You might expose this behind an admin action (e.g. “Log out everywhere”).


# 4) Protect X-Forwarded-For

# If using X-Forwarded-For you must ensure your reverse proxy (nginx)
#  sets it and Flask is aware/trusted. 
# If you don't control it properly, an attacker can forge IPs.


class PgSession(CallbackDict, SessionMixin):
    """Reprezentuje jednu flaskovou session uloženou v Postgresu.


    Dědí z CallbackDict, aby bylo možné detekovat změny (atribut `modified`).
    
    
    Parametry
    ---------
    initial: dict | None
    Počáteční data session.
    sid: str | None
    Session ID (opaque token uložený v cookie).
    new: bool
    True pokud jde o nově vytvořenou session.
    """
    def __init__(self, initial=None, sid=None, new=False):
        def _on_update(self):
            self.modified = True
        super().__init__(initial or {}, _on_update)
        self.sid = sid
        self.new = new
        self.modified = False


def short_ua_hash(user_agent: str) -> str:
    """Vrátí zkrácený (16 hex znaků) SHA-256 hash user-agenta.


    Používá se pro základní detekci změny user-agenta mezi požadavky
    bez uložení celého stringu UA do tabulky.
    """
    # return first 16 hex chars of sha256
    if not user_agent:
        return ''
    return hashlib.sha256(user_agent.encode('utf-8')).hexdigest()[:16]


def client_ip_from_request() -> str:
    """Získej klientskou IP adresu z požadavku.


    Nejprve se pokusí použít hlavičku X-Forwarded-For (první IP v seznamu),
    pokud není nastavena, použije `request.remote_addr`.
    
    
    POZOR: pokud přijímáte požadavky přes reverzní proxy, je nezbytné
    zajistit, aby proxy správně předávala tuto hlavičku a aby jí bylo důvěřováno.
    """
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


class PgSessionInterface(SessionInterface):
    """SessionInterface ukládající sessiony do PostgreSQL tabulky.


    Vlastní implementace metod:
    - open_session: načte session z DB podle sid z cookie.
    - save_session: uloží/aktualizuje session v DB a nastaví cookie.
    
    
    Parametry
    ---------
    get_db_pool: callable
    Funkce pro získání DB pool (defaultně cashier_app.db.get_pool).
    table: str
    Název DB tabulky, kam se session ukládají (výchozí 'sessions').
    """
    serializer = json
    session_class = PgSession

    def __init__(self, get_db_pool=get_pool, table='sessions'):
        self.get_pool = get_db_pool
        self.table = table

    def generate_sid(self):
        """Vygeneruje náhodné SID použité jako hodnota cookie.


        Používá secure token_urlsafe(32) pro dostatečnou entropii.
        """
        return secrets.token_urlsafe(32)

    def get_expiration_time(self, app, session):
        """Vrátí datetime expirace pro cookie nebo None.


        Pokud je session označená jako `permanent`, použije se
        `app.permanent_session_lifetime` a vrátí se UTC datetime.
        Jinak vrací None (session-cookie bez expirace -> prohlížeč končí session při zavření).
        """
        if session.permanent:
            return datetime.datetime.now(datetime.timezone.utc) + app.permanent_session_lifetime
        return None
    
    def open_session(self, app, request):
        """Načte session z DB na základě cookie SID.


        Kontroluje expiraci a -- volitelně -- UA/IP pokud je v konfiguraci
        povoleno (SESSION_ENFORCE_UA / SESSION_ENFORCE_IP). Pokud session
        neexistuje nebo je neplatná, vrátí novou prázdnou session.
        """
        sid = request.cookies.get(app.config.get("SESSION_COOKIE_NAME", "session"))
        if not sid:
            return self.session_class(sid=None, new=True)

        pool = self.get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                row = cur.execute(f'''
                    SELECT data, employee_id, ip, ua_hash, expires_at
                    FROM {self.table}
                    WHERE id = %s''',
                    (sid,)).fetchone()
        if not row:
            return self.session_class(sid=None, new=True)
        
        if row['expires_at'] is not None and row['expires_at'] < datetime.datetime.now(datetime.timezone.utc):
            # expired
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f'''
                        DELETE FROM {self.table}
                        WHERE id = %s''',
                        (sid,))
            return self.session_class(sid=None, new=True)
        
        enforce_ua = app.config.get('SESSION_ENFORCE_UA', False)
        enforce_ip = app.config.get('SESSION_ENFORCE_IP', False)

        if enforce_ua or enforce_ip:
            actual_ua_hash = short_ua_hash(request.headers.get('User-Agent', ''))
            actual_ip = client_ip_from_request()

            if enforce_ua and row['ua_hash'] and row['ua_hash'] != actual_ua_hash:
                # UA mismatch -> invalidate session
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(f"DELETE FROM {self.table} WHERE id = %s", (sid,))
                return self.session_class(sid=None, new=True)

            if enforce_ip and row['ip'] and row['ip'] != actual_ip:
                # IP mismatch -> invalidate
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(f"DELETE FROM {self.table} WHERE id = %s", (sid,))
                return self.session_class(sid=None, new=True)
        
        data = row['data'] or {}
        return self.session_class(initial=data, sid=sid, new=False)
    
    def save_session(self, app, session, response):
        """Uloží session do DB a nastaví cookie v odpovědi.


        Pokud je session prázdná, smaže se z DB a cookie je odstraněna.
        Pokud je session nová nebo pokud došlo k regeneraci SID, vygeneruje se
        nový sid a starý (pokud existuje) se odstraní.
        """
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        # je zde, aby se regenerate vždy odstranilo
        regenerate = session.pop('_regenerate', False)

        # if session is empty -> delete cookie and DB row
        if not session:
            if session.sid:
                pool = self.get_pool()
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f'''
                            DELETE FROM {self.table}
                            WHERE id = %s''',
                            (session.sid,))

            response.delete_cookie(
                app.config.get("SESSION_COOKIE_NAME", "session"),
                domain=domain,
                path=path
            )
            return
        
        # Decide if we need a new sid (new session or explicit regeneration)
        sid = session.sid
        if session.new or not sid or regenerate:
            new_sid = self.generate_sid()
        else:
            new_sid = sid

        expires = self.get_expiration_time(app, session)
        data = dict(session) # JSON serializable items only

        # extra metadata: employee_id (if present), ua_hash, ip
        employee_id = data.get('employee_id')
        ua_hash = short_ua_hash(request.headers.get('User-Agent', ''))
        ip = client_ip_from_request()

        pool = self.get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.table} (id, data, employee_id, ip, ua_hash, modified_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, now(), %s)
                    ON CONFLICT (id) DO UPDATE
                    SET data = EXCLUDED.data,
                    employee_id = EXCLUDED.employee_id,
                    ip = EXCLUDED.ip,
                    ua_hash = EXCLUDED.ua_hash,
                    modified_at = now(),
                    expires_at = EXCLUDED.expires_at
                    """,
                    (new_sid, Json(data), employee_id, ip, ua_hash, expires))

                if (new_sid != sid) and sid:
                    try:
                        cur.execute(f"""
                            DELETE FROM {self.table}
                            WHERE id = %s""",
                            (sid,))
                    except Exception:
                        # Ignore delete errors — not fatal; transaction still succeeds.
                        pass

        session.sid = new_sid
        session.new = False
                
        # set cookie (the cookie value is the opaque sid)
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


# --- small helper to delete expired sessions (callable from CLI/cron) ------
def delete_expired_sessions(pool=None, max_inactive_days: int | None = None) -> int:
    """Smaže z DB expirované sessiony a (volitelně) staré řádky bez expires_at.


    Parametry
    ---------
    conn: psycopg.Connection | None
    Volitelný pool pro DB. Pokud None, použije se get_pool().
    max_inactive_days: int | None
    Pokud je zadáno, smaže i řádky kde expires_at IS NULL a upraveno bylo
    více než `max_inactive_days` dní.
    
    
    Vrací
    -----
    int
    Počet smazaných řádků.
    """
    """
    Delete expired sessions and optionally stale session-cookie rows (expires_at IS NULL).
    Returns number of deleted rows.
    If max_inactive_days is None, reads app.config['SESSION_MAX_INACTIVE_DAYS'] when run under app context,
    otherwise uses provided value. If the final threshold is None, only deletes rows with a non-null expires_at.
    """
    close_conn = False
    if pool is None:
        pool = get_pool()
        close_conn = True

    if max_inactive_days is None:
        try:
            from flask import current_app, has_app_context
            if has_app_context():
                max_inactive_days = current_app.config.get('SESSION_MAX_INACTIVE_DAYS', None)
        except Exception:
            pass

    deleted = 0

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM sessions
                WHERE expires_at IS NOT NULL AND expires_at < now()
                RETURNING id;
                """)
            deleted += len(cur.fetchall())

            if max_inactive_days is not None:
                days = float(max_inactive_days)
                cur.execute(f"""
                    DELETE FROM sessions
                    WHERE expires_at IS NULL
                      AND modified_at < now() - interval '{days} days'
                    RETURNING id;
                    """)
                deleted += len(cur.fetchall())

    if close_conn:
        try:
            conn.close()
        except Exception:
            pass
    return deleted

import click
from flask import current_app

@click.command('clear-sessions')
def clear_sessions_command():
    """Delete expired sessions from DB."""
    deleted = delete_expired_sessions()
    click.echo(f"Deleted {deleted} expired sessions.")


# Option A — Cron (recommended for many simple deployments)

# Create a small shell script that runs your Flask CLI command (this assumes you added the clear-sessions CLI command described earlier).

# Create /usr/local/bin/clear_sessions.sh (adjust paths/user):

# #!/usr/bin/env bash
# # /usr/local/bin/clear_sessions.sh
# # Runs the Flask CLI 'clear-sessions' command for the cashier_app
# # Make sure this file is executable: sudo chmod 755 /usr/local/bin/clear_sessions.sh

# # environment: change these to match your deployment
# export PATH="/home/deploy/.local/bin:/home/deploy/venv/bin:$PATH"   # ensure python & flask in PATH
# export VENV="/home/deploy/venv"               # optional: path to virtualenv
# export FLASK_APP="cashier_app"
# # if you need DB or other env vars set for create_app() to work:
# export CASHIER_APP_SECRET="replace-with-real-secret"
# export DATABASE_CONNINFO="dbname=cashier_app host=localhost user=postgres password=heslo123 port=5432"
# # add any other env vars your app depends on

# # activate venv (optional)
# if [ -f "$VENV/bin/activate" ]; then
#   # shellcheck source=/dev/null
#   . "$VENV/bin/activate"
# fi

# # run the command and capture output
# LOGFILE="/var/log/clear_sessions.log"
# echo "=== $(date -Iseconds) Starting clear-sessions ===" >> "$LOGFILE"
# # run using flask CLI
# flask --app "$FLASK_APP" clear-sessions >> "$LOGFILE" 2>&1
# STATUS=$?
# echo "=== $(date -Iseconds) Done clear-sessions exit=$STATUS ===" >> "$LOGFILE"
# exit $STATUS


# Make it executable:

# sudo chmod +x /usr/local/bin/clear_sessions.sh
# sudo chown deploy:deploy /usr/local/bin/clear_sessions.sh  # set appropriate owner
# sudo touch /var/log/clear_sessions.log
# sudo chown deploy:deploy /var/log/clear_sessions.log


# Add a crontab entry for the deploy user (run crontab -e as that user). Example: run every hour:

# 0 * * * * /usr/local/bin/clear_sessions.sh


# Or every 15 minutes:

# */15 * * * * /usr/local/bin/clear_sessions.sh


# Crontab logging: the script logs to /var/log/clear_sessions.log so you can inspect what happened.

# Notes

# Ensure flask and your virtualenv are on PATH, or call it with full path (/home/deploy/venv/bin/flask).

# Set any necessary environment vars (DB conn info, secrets) in the script or in the user crontab.

# Run as a non-root user (e.g., deploy or www-data) that has permission to use your DB.
