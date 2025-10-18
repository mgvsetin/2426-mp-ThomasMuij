from flask import Flask
import os

# název funkce je důležitý, aby ji flask spustil
def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY = 'dev', # ?$ python -c 'import secrets; print(secrets.token_hex())'?
        DATABSE_CONNINFO = """
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
        }
    )

    os.makedirs(app.instance_path, exist_ok=True)

    if test_config is None:
        app.config.from_pyfile('config.py')
    else:
        app.config.from_mapping(test_config)

    
    @app.route('/temporary/config') # remove this
    def temporary():
        response = [str(k) for k in app.config.items()]
        response.append(app.instance_path)
        return response
    
    from cashier_app import db
    db.init_app(app)

    from cashier_app import auth
    app.register_blueprint(auth.bp)

    from cashier_app import session
    app.register_blueprint(session.bp)

    from cashier_app import order
    app.register_blueprint(order.bp)
    # aby fungovalo i url_for('index') (ne jenom url_for('order.index'))
    app.add_url_rule('/', endpoint='index')

    return app