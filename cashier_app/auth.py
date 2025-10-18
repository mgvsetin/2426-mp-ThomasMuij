import functools
from flask import Blueprint, request, render_template, current_app, session, redirect, url_for, g
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from cashier_app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        valid_credentials = True
        
        with get_db() as conn:
            with conn.cursor() as cur:
                account = cur.execute('''
                                      SELECT id, username, password_hash
                                      FROM account
                                      WHERE username = %s AND deleted_at IS NULL''',
                                      (username,)).fetchone()
        
        password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])

        if not account:
            valid_credentials = False
        else:
            try:
                password_hasher.verify(account['password_hash'], password)
            except (VerifyMismatchError, VerificationError):
                valid_credentials = False
        
        if valid_credentials:
            if password_hasher.check_needs_rehash(account['password_hash']):
                new_hash = password_hasher.hash(password)
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute('''UPDATE account
                                    SET password_hash = %s
                                    WHERE id = %s''',
                                    (new_hash, account['id']))
                        
            session.clear()
            session['account_id'] = account['id']
            return redirect(url_for('order.index'))
        
        session.clear()
        session['login_error'] = True

    # letwebserver (nginx?) serve static files for performance; Flask can still send_static_file during development.
    return current_app.send_static_file('login.html')


@bp.before_app_request
def load_logged_in_user():
    account_id = session.get('account_id')

    if account_id is None:
        g.account = None
    else:
        with get_db() as conn:
            with conn.cursor() as cur:
                g.account = cur.execute(
                    '''
                    SELECT * FROM account
                    WHERE id = %s AND deleted_at IS NULL''',
                    (account_id,)).fetchone()


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.account is None:
            return redirect(url_for('auth.login'))
        
        return view(**kwargs)
    
    return wrapped_view


@bp.route('/pick-event', methods=('POST',))
@login_required
def pick_event():
    event_id = request.form.get('event_id')
    account_id = session['account_id']

    with get_db() as conn:
        with conn.cursor() as cur:
            role = cur.execute(
                '''
                SELECT role
                FROM account_event_roles
                WHERE account_id = %s AND event_id = %s''',
                (account_id, event_id)).fetchone()['role']
            
            return role