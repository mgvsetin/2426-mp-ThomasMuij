"""Modul pro správu PostgreSQL připojení v kontextu Flask aplikace.


Funkce get_db zajišťuje znovupoužití existujícího spojeni uloženého v `g` pokud
parametry připojení souhlasí, jinak vytvoří nové.
"""

from flask import current_app
import click
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import logging
import atexit

logger = logging.getLogger(__name__)


def get_pool() -> ConnectionPool:
    # vždy použij pool/get_pool().connection() as ...:
    # = context manager, aby se connection vrátilo
    pool: ConnectionPool = current_app.extensions.get('db_pool')
    if pool is None:
        raise RuntimeError("db pool not initialized")
    return pool


def init_db():
    """Inicializuje databázi podle souboru schema.sql v instanci aplikace.


    Načte SQL ze souboru schema.sql a vykoná ho přes připojení.
    """
    with current_app.open_resource('schema.sql', 'r', 'utf-8') as f:
        sql = f.read()

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


@click.command('init-db') # flask --app cashier_app init-db
def init_db_command():
    """CLI příkaz pro inicializaci databáze.


    Tento příkaz registruje `flask --app cashier_app init-db`.
    """
    init_db()
    click.echo('Initialized the database.')

from flask import Flask
def init_app(app: Flask):
    # app.extensions = getattr(app, "extensions", {})
    conninfo = app.config.get('DATABASE_CONNINFO')
    pool = ConnectionPool(
        conninfo,
        kwargs={'row_factory': dict_row},
        min_size=1,
        max_size=5,
        timeout=30,
        # check=ConnectionPool.check_connection,
        open=True) # if process can be preloaded and then forked, use open=False and call pool.open() after fork
    app.extensions['db_pool'] = pool

    # není nutné
    def _close_pool():
        try:
            pool.close(timeout=2.0)
        except Exception:
            logger.exception("closing pool failed")
    atexit.register(_close_pool)

    app.cli.add_command(init_db_command)