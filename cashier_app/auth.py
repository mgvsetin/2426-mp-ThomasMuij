import functools
from urllib.parse import urlparse, urljoin
from flask import Blueprint, request, render_template, current_app, session, redirect, url_for, g, jsonify
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cashier_app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

# CSRF protection
# No brute-force protection / rate-limiting / logging of failed attempts
# Add IP-based rate limiting (e.g. Flask-Limiter) and/or account lockouts after N failed attempts. Log failed login attempts with limited detail (don't log the password).
# db error handling


def get_employee_id(username_or_email: str, password: str) -> str | None:
    conn = get_db()

    with conn.transaction():
        with conn.cursor() as cur:
            employee = cur.execute('''
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
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE employees
                    SET password_hash = %s
                    WHERE id = %s''',
                    (new_hash, employee['id']))
    
    return employee['id']


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username-email', '').strip()
        password = request.form.get('password', '')

        employee_id = get_employee_id(username_or_email, password)

        if employee_id:
            session.clear()
            # request that the session cookie be replaced with a new sid when saved
            session['_regenerate'] = True
            session['employee_id'] = str(employee_id)

            # session.permanent = True

            return jsonify(redirect_url=url_for('order.index')), 200

        session.clear()
        return jsonify(error='invalid_credentials'), 401

    # letwebserver (nginx?) serve static files for performance; Flask can still send_static_file during development.
    return current_app.send_static_file('login/login.html')


def load_logged_in_employee() -> dict | None:
    employee_id = session.get('employee_id')

    if employee_id is None:
        g.employee = None
        return g.employee

    conn = get_db()
    with conn.transaction():
        with conn.cursor() as cur:
            g.employee = cur.execute('''
                SELECT id, username, email, is_admin
                FROM employees
                WHERE id = %s AND deleted_at IS NULL''',
                (employee_id,)).fetchone()
            
    return g.employee


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         load_logged_in_employee()
#         if g.employee is None:
#             return redirect(url_for('auth.login'))
        
#         return view(**kwargs)
    
#     return wrapped_view
