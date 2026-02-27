"""Modul pro autentizaci zaměstnanců.

Obsahuje blueprinty pro přihlášení a odhlášení zaměstnanců a pomocné funkce
pro ověření přihlašovacích údajů a načtení přihlášeného zaměstnance ze session.
"""

from uuid import UUID
import functools
from flask import Blueprint, request, render_template, current_app, session, redirect, url_for, g, jsonify
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cashier_app.db import get_pool
from cashier_app import limiter


bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login')
def get_login_page():
    """Vrátí HTML stránku pro přihlášení."""
    return render_template('login/login.html')


api_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')



def get_employee_id(username_or_email: str) -> str | UUID | None:
    """Vyhledá zaměstnance podle uživatelského jména nebo e-mailu a vrátí jeho ID.

    Vrátí UUID zaměstnance, pokud existuje a nebyl smazán, jinak vrátí None.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id
                FROM employees
                WHERE (LOWER(username) = %s OR LOWER(email) = %s)
                AND deleted_at IS NULL''',
                (username_or_email.lower(), username_or_email.lower())).fetchone()
    
    if not employee:
        return None
    
    return employee['id']


def employee_password_is_correct(employee_id: str, password: str):
    """Ověří, zda zadané heslo odpovídá heslu zaměstnance.

    Pokud je hash hesla zastaralý, provede rehashování a uloží nový hash do databáze.
    Vrátí True při správném hesle, jinak False.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            employee = cur.execute(
                '''
                SELECT id, password_hash
                FROM employees
                WHERE id = %s
                AND deleted_at IS NULL''',
                (employee_id,)).fetchone()
            
    if not employee:
        return False
    
    password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])

    try:
        password_hasher.verify(employee['password_hash'], password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    
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
    
    return True


@api_bp.route('/login', methods=('POST',))
@limiter.limit("10 per 15 minutes")
def login():
    """Zpracuje POST požadavek pro přihlášení zaměstnance.

    Ověří přihlašovací údaje, vytvoří novou session a vrátí URL pro přesměrování.
    Při neúspěchu vrátí chybu 401.
    """
    # if request.method == 'POST':
    username_or_email = request.form.get('username-email', '').strip()
    password = request.form.get('password', '')
    remember_me = request.form.get('remember-me')

    employee_id = get_employee_id(username_or_email)

    if employee_id and employee_password_is_correct(employee_id, password):
        session.clear()
        # požadavek na nahrazení session cookie novým SID při uložení
        session['_regenerate'] = True
        session['employee_id'] = str(employee_id)

        if remember_me:
            session.permanent = True

        return jsonify(redirect_url=url_for('index.get_index_page')), 201

    session.clear()
    return jsonify(error='invalid_credentials'), 401

    # return current_app.send_static_file('html/login/login.html')


def load_logged_in_employee() -> dict | None:
    """Načte přihlášeného zaměstnance ze session a uloží ho do kontextu požadavku `g`.

    Pokud v session není žádné employee_id, nastaví g.employee na None.
    Vrátí slovník s údaji o zaměstnanci nebo None, pokud není přihlášen.
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
    """Odhlásí aktuálního zaměstnance vymazáním session a přesměruje na přihlašovací stránku."""
    session.clear()
    return redirect(url_for('auth.get_login_page'))


def require_login(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        load_logged_in_employee()
        if g.employee is None:
            return jsonify(redirect_url=url_for('auth.get_login_page')), 401
        
        return view(**kwargs)
    
    return wrapped_view


def require_admin(view):
    @functools.wraps(view)
    @require_login
    def wrapped_view(**kwargs):
        if not g.employee['is_admin']:
            return jsonify(error='insufficient_privileges'), 403

        return view(**kwargs)

    return wrapped_view