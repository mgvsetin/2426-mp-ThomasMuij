from flask import Flask
import os

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY = 'dev',
        DATABSE_CONNINFO = """
            dbname=cashier_system
            host=localhost
            user=postgres
            password=heslo123
            port=5432"""
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
    
    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    return app