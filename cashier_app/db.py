from flask import g, current_app
import click
import psycopg
from psycopg.rows import namedtuple_row


def get_db(row_factory=namedtuple_row, **kwargs):
    if 'db' not in g:
        conninfo = current_app.config['DATABSE_CONNINFO']
        
        g.db = psycopg.connect(conninfo, row_factory=row_factory, **kwargs)
        g

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_db():
    with current_app.open_resource('schema.sql', 'r', 'utf-8') as f:
        sql = f.read()

    with get_db(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


@click.command('init-db') # flask --app cashier_app init-db
def init_db_command():
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)