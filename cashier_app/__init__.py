"""Inicializačni modul aplikace Flask pro cashier_app.
Obsahuje funkci create_app, ktera vytvori a nakonfiguruje Flask aplikaci,
registruje blueprinty a nastavuje session interface.
"""

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
import os
from datetime import datetime, date, timezone
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix


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
            port=5432
            options='-c timezone=UTC'""",
        PASSWORD_HASHER_PARAMETERS = {
            'time_cost': 3,
            'memory_cost': 65536,
            'parallelism':2,
            'hash_len': 32,
            'salt_len':16
        },
        READER_INFO = {
            # musí být a všechno je povinné
            'serial_port_options': {
                'baudRate': 9600, 
                'dataBits': 8,
                'stopBits': 1,
                'parity': 'none',
                'flowControl': 'none'
            },
            # když není, můžou se v prohlížeči vybrat všechny připojené čtečky
            # když je, tak musí mít každý slovník usbVendorId a může mít usbProductId
            # každý slovník přidá navíc možnosti
            # usbVendorId: An unsigned short integer that identifies a USB device vendor. The USB Implementors Forum assigns IDs to specific vendors.
            # usbProductId: An unsigned short integer that identifies a USB device. Each vendor assigns IDs to its products.
            # 'filters': [
            #     {'usbVendorId': 4292, 'usbProductId': 60000}
            # ]
        },
        MAX_UNDO_CHANGES = 30,
        UNDO_TIME_LIMIT_MINUTES = 60,
        UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads', 'products'),
        UPLOAD_IMAGE_PIXEL_LIMIT = 50_000_000,
        ALLOWED_IMAGE_EXTENSIONS = {'jpeg', 'png', 'webp'},
        ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'},
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024,  # 16MB
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
    os.makedirs(app.config.get('UPLOAD_FOLDER'), exist_ok=True)
    with open(os.path.join(app.instance_path, 'config.py'), 'a') as f:
        pass

    if test_config is None:
        app.config.from_pyfile('config.py')
    else:
        app.config.from_mapping(test_config)


    # pouze když je nastavený nginx (nebo jiný proxy server), nastavení x_for=1... musí být přesná
    app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )


    # @app.before_request
    # def simulate_slow_connection():
    #     import time
    #     time.sleep(2)



    @app.route('/test', methods=('POST', 'GET'))
    def test():
        from flask import url_for, jsonify, request
        with open('prints.txt', 'a', encoding='utf-8') as f:
            print(request.form.get('remove-image'), file=f)

        return jsonify(), 200

        

    # není nutné, ale js teoreticky bere pouze ISO 8601
    # prakticky funguje i default, ale nemusí vždy fungovat
    class ISOJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                if isinstance(obj, date) and not isinstance(obj, datetime):
                    return obj.isoformat()
                if obj.tzinfo is None:
                    obj = obj.replace(tzinfo=timezone.utc)

                return obj.astimezone(timezone.utc).isoformat()
            
            return super().default(obj)
    
    app.json = ISOJSONProvider(app)
    
    from cashier_app import db
    db.init_app(app)

    from cashier_app.pg_session import PgSessionInterface, delete_expired_sessions
    from datetime import timedelta
    app.permanent_session_lifetime = timedelta(days=7)

    app.session_interface = PgSessionInterface(get_db_pool=db.get_pool)

    from cashier_app.pg_session import clear_sessions_command
    app.cli.add_command(clear_sessions_command)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(e):
        return jsonify(error="file_too_large"), 413

    # make sure nginx does this
    @app.route('/uploads/products/<path:filename>')
    def uploaded_product_image(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    from cashier_app import auth
    app.register_blueprint(auth.bp)
    app.register_blueprint(auth.api_bp)

    from cashier_app import session_api
    app.register_blueprint(session_api.api_bp)

    from cashier_app import index
    app.register_blueprint(index.bp)
    # maybe make a general index for employees and users

    from cashier_app import employee_events_booths
    app.register_blueprint(employee_events_booths.api_bp)

    from cashier_app import employees
    app.register_blueprint(employees.bp)
    app.register_blueprint(employees.api_bp)

    from cashier_app import events
    app.register_blueprint(events.bp)
    app.register_blueprint(events.api_bp)

    from cashier_app import reader_info
    app.register_blueprint(reader_info.api_bp)

    from cashier_app import transactions
    app.register_blueprint(transactions.api_bp)

    from cashier_app import users_and_wallets
    app.register_blueprint(users_and_wallets.api_bp)

    from cashier_app import paste
    app.register_blueprint(paste.api_bp)

    from cashier_app import undo_and_redo
    app.register_blueprint(undo_and_redo.bp)

    from cashier_app import settings
    app.register_blueprint(settings.bp)
    app.register_blueprint(settings.api_bp)

    # @app.after_request
    # def print_sum(a):
    #     with open(r'C:\Users\thoma\Documents\code\2426-mp-ThomasMuij\prints.txt', 'a', encoding='utf-8') as f:
    #         # import pprint
    #         # pprint.pprint(db.get_pool().get_stats(), stream=f)
    #         # print('\n', file=f)
    #         with db.get_pool().connection() as conn:
    #             with conn.cursor() as cur:
    #                 cur.execute("SHOW TIMEZONE")
    #                 print(cur.fetchone(), file=f)   # should be ('UTC',)
    #     return a

    return app
