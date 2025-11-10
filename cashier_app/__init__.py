"""Inicializačni modul aplikace Flask pro cashier_app.
Obsahuje funkci create_app, ktera vytvori a nakonfiguruje Flask aplikaci,
registruje blueprinty a nastavuje session interface.
"""

from flask import Flask
import os


# název funkce je důležitý, aby ji flask spustil
def create_app(test_config=None):
    """Vytvoří a nakonfiguruje Flask aplikaci.


    Parametry
    ---------
    test_config: dict | None
    Volitelný slovník konfigurace, který přepíše konfiguraci z config.py
    (využívá se především pro testování).
    
    
    Vrátí
    ------
    Flask
    Nakonfigurovaná Flask aplikace.
    """
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY = os.environ.get('CASHIER_APP_SECRET') or 'dev', # ?$ python -c 'import secrets; print(secrets.token_hex())'?, secrets.token_urlsafe(32)
        DATABASE_CONNINFO = os.environ.get('DATABASE_CONNINFO') or """
            dbname=cashier_app
            host=localhost
            user=postgres
            password=heslo123
            port=5432""",
        PASSWORD_HASHER_PARAMETERS = {
            'time_cost': 3,
            'memory_cost': 65536,
            'parallelism':2,
            'hash_len': 32,
            'salt_len':16
        },
        SESSION_COOKIE_HTTPONLY = True, # JavaScript nemůže číst cookies
        SESSION_COOKIE_SAMESITE = 'Lax',   # or 'Strict' if you can
        SESSION_COOKIE_SECURE = False,
        # SESSION_COOKIE_SECURE should be True in production when using HTTPS
        # SESSION_COOKIE_SECURE = bool(os.environ.get('CASHIER_APP_COOKIE_SECURE', False)),

        SESSION_ENFORCE_UA = False,
        SESSION_ENFORCE_IP = False,
        SESSION_MAX_INACTIVE_DAYS = 7
    )

    os.makedirs(app.instance_path, exist_ok=True)
    with open(os.path.join(app.instance_path, 'config.py'), 'a') as f:
        pass

    if test_config is None:
        app.config.from_pyfile('config.py')
    else:
        app.config.from_mapping(test_config)


    # @app.before_request
    # def simulate_slow_connection():
    #     import time
    #     time.sleep(1)

    
    @app.route('/temporary/config') # remove this
    def temporary():
        response = [str(k) for k in app.config.items()]
        response.append(app.instance_path)
        return response
    
    from cashier_app import db
    db.init_app(app)

    from cashier_app.pg_session import PgSessionInterface, delete_expired_sessions
    from datetime import timedelta
    app.permanent_session_lifetime = timedelta(days=7)

    app.session_interface = PgSessionInterface(get_db_fn=db.get_db)

    from cashier_app.pg_session import clear_sessions_command
    app.cli.add_command(clear_sessions_command)

    from cashier_app import auth
    app.register_blueprint(auth.bp)

    from cashier_app import session_api
    app.register_blueprint(session_api.bp)

    from cashier_app import index
    app.register_blueprint(index.bp)
    # aby fungovalo i url_for('index') (ne jenom url_for('order.index'))
    app.add_url_rule('/', endpoint='index') # maybe remove, make a general index for employees and users

    from cashier_app import events_booths
    app.register_blueprint(events_booths.bp)

    from cashier_app import employee_manager
    app.register_blueprint(employee_manager.bp)

    from cashier_app import employees
    app.register_blueprint(employees.bp)

    from cashier_app import event_manager
    app.register_blueprint(event_manager.bp)

    return app
