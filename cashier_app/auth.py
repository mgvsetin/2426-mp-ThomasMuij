from flask import Blueprint, request, render_template
from cashier_app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    account_type = request.args.get('account_type')

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        
        with get_db() as conn:
            with conn.cursor() as cur:
                user = cur.execute('SELECT * FROM account WHERE username = ? AND type = ?', (username, account_type)).fetchone()
        
        if user is None:
            error = 'Incorrect username.'
        # elif not verify password

    return render_template('auth/login.html')