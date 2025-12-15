"""Modul pro autentizaci zaměstnanců.

Obsahuje blueprint /auth s routami pro login, logout a pomocné funkce pro nahrání
přihlášeného zaměstnance.
"""

import functools
from urllib.parse import urlparse, urljoin
from flask import Blueprint, request, render_template, current_app, session, redirect, url_for, g, jsonify
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cashier_app.db import get_pool


bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login')
def get_login_page():
    return current_app.send_static_file('html/login/login.html')


api_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')

# CSRF protection
# No brute-force protection / rate-limiting / logging of failed attempts
# Add IP-based rate limiting (e.g. Flask-Limiter) and/or account lockouts after N failed attempts. Log failed login attempts with limited detail (don't log the password).
# db error handling


def get_employee_id(username_or_email: str, password: str) -> str | None:
    """Ověří zadané uživatelské jméno/e-mail a heslo, vrátí id zaměstnance.


    Postup:
    1. Najde záznam zaměstnance podle username nebo email (pokud existuje a není smazaný).
    2. Ověří heslo pomocí Argon2.
    3. Pokud je potřeba, přehashuje heslo a uloží nový hash.
    
    
    Parametry
    ---------
    username_or_email: str
    Uživatelské jméno nebo e-mail zadaný do přihlašovacího formuláře.
    password: str
    Nehashované heslo z formuláře.
    
    
    Vrací
    -----
    str | None
    ID zaměstnance (řetězec) pokud ověření proběhlo úspěšně, jinak None.
    """

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id, password_hash
                FROM employees
                WHERE (username = %s OR email = %s)
                AND deleted_at IS NULL''',
                (username_or_email, username_or_email)).fetchone()
    
    password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])

    if not employee:
        return None

    try:
        password_hasher.verify(employee['password_hash'], password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return None
    
    if password_hasher.check_needs_rehash(employee['password_hash']):
        new_hash = password_hasher.hash(password)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    UPDATE employees
                    SET password_hash = %s
                    WHERE id = %s''',
                    (new_hash, employee['id']))
    
    return employee['id']


@api_bp.route('/login', methods=('POST',))
def login():
    """View pro přihlášení zaměstnance.


    Zpracovává oba způsoby:
    - GET: vrátí statickou HTML stránku přihlášení (pro vývoj/produkci lze použít webserver)
    - POST: zpracuje přihlašovací údaje, vytvoří session a vrátí JSON s redirect_url nebo chybu.
    """
    # if request.method == 'POST':
    username_or_email = request.form.get('username-email', '').strip()
    password = request.form.get('password', '')
    remember_me = request.form.get('remember-me')

    employee_id = get_employee_id(username_or_email, password)

    if employee_id:
        session.clear()
        # request that the session cookie be replaced with a new sid when saved
        session['_regenerate'] = True
        session['employee_id'] = str(employee_id)

        if remember_me:
            session.permanent = True

        return jsonify(redirect_url=url_for('index.get_index_page')), 201

    session.clear()
    return jsonify(error='invalid_credentials'), 401

    # letwebserver (nginx?) serve static files for performance; Flask can still send_static_file during development.

    # return current_app.send_static_file('html/login/login.html')


def load_logged_in_employee() -> dict | None:
    """Načte aktuálně přihlášeného zaměstnance z session a ulož do `g`.


    Vrátí slovník s informacemi o zaměstnanci nebo None pokud není přihlášen.
    """
    employee_id = session.get('employee_id')

    if employee_id is None:
        g.employee = None
        return g.employee

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            g.employee = cur.execute(
                '''
                SELECT id, username, email, is_admin
                FROM employees
                WHERE id = %s AND deleted_at IS NULL''',
                (employee_id,)).fetchone()
            
    return g.employee


@api_bp.route('/logout')
def logout():
    """Odhlásí aktuálního uživatele clearnutím session a přesměrová na login.
    """
    session.clear()
    return redirect(url_for('auth.get_login_page'))


# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         load_logged_in_employee()
#         if g.employee is None:
#             return redirect(url_for('auth.login'))
        
#         return view(**kwargs)
    
#     return wrapped_view
