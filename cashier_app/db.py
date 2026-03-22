"""Modul pro správu fondu (poolu) PostgreSQL připojení v rámci Flask aplikace.

Poskytuje funkce pro inicializaci a získání sdíleného fondu připojení,
inicializaci databázového schématu a CLI příkaz pro nastavení databáze.
"""

from flask import current_app
import click
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import logging
import atexit

logger = logging.getLogger(__name__)


def get_pool() -> ConnectionPool:
    """Vrátí fond připojení (ConnectionPool) z rozšíření aktuální Flask aplikace.

    Vyvolá RuntimeError, pokud fond připojení nebyl inicializován.
    """
    # vždy použij pool/get_pool().connection() as ...:
    # = context manager, aby se connection vrátilo
    pool: ConnectionPool = current_app.extensions.get('db_pool')
    if pool is None:
        raise RuntimeError("db pool not initialized")
    return pool


def init_db():
    """Inicializuje databázové schéma spuštěním souboru schema.sql.

    Načte obsah souboru schema.sql z prostředků aplikace a provede
    všechny SQL příkazy v rámci jednoho připojení z fondu.
    """
    with current_app.open_resource('schema.sql', 'r', 'utf-8') as f:
        sql = f.read()

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


    # TODO: remove this
    # development values:
    with current_app.open_resource('development_values.sql', 'r', 'utf-8') as f:
        dev_values = f.read()

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(dev_values)


@click.command('init-db') # flask --app cashier_app init-db
def init_db_command():
    """CLI příkaz pro inicializaci databáze.

    Spustí inicializaci databázového schématu. Registruje se jako
    ``flask --app cashier_app init-db``.
    """
    init_db()
    click.echo('Initialized the database.')

from flask import Flask
def init_app(app: Flask):
    """Inicializuje fond připojení k databázi a zaregistruje CLI příkazy.

    Vytvoří ConnectionPool na základě konfigurace aplikace, uloží ho
    do ``app.extensions`` a zaregistruje úklidovou funkci při ukončení procesu.
    """
    # app.extensions = getattr(app, "extensions", {})
    conninfo = app.config.get('DATABASE_CONNINFO')
    pool = ConnectionPool(
        conninfo,
        kwargs={'row_factory': dict_row},
        min_size=1,
        max_size=5,
        timeout=30,
        # check=ConnectionPool.check_connection,
        open=True) # pokud se proces předem načte a poté forkne, použij open=False a zavolej pool.open() po forku
    app.extensions['db_pool'] = pool

    # není nutné
    def _close_pool():
        """Uzavře fond připojení při ukončení procesu."""
        try:
            pool.close(timeout=2.0)
        except Exception:
            logger.exception("closing pool failed")
    atexit.register(_close_pool)

    app.cli.add_command(init_db_command)