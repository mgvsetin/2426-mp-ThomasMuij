"""Modul pro správu fondu (poolu) PostgreSQL připojení v rámci Flask aplikace.

Poskytuje funkce pro inicializaci a získání sdíleného fondu připojení,
inicializaci databázového schématu, zálohování a obnovu databáze
a CLI příkazy pro správu databáze.
"""

from flask import current_app
from flask.cli import with_appcontext
import click
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg import IntegrityError
import logging
import atexit
import subprocess
import os
from datetime import datetime, timezone

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


def insert_development_values():
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


@click.command('insert-development-values') # flask --app cashier_app insert-development-values
def insert_development_values_command():
    """CLI příkaz pro vložení zkušebních dat do databáze.

    Registruje se jako ``flask --app cashier_app insert-development-values``.
    """
    insert_development_values()
    click.echo('Inserted development values.')


@click.command('create-admin')  # flask --app cashier_app create-admin
@with_appcontext
def create_admin_command():
    """CLI příkaz pro vytvoření administrátorského zaměstnance.

    Interaktivně vyžádá uživatelské jméno, e-mail a heslo a vytvoří
    nového zaměstnance s is_admin=TRUE.
    Registruje se jako ``flask --app cashier_app create-admin``.
    """
    from argon2 import PasswordHasher
    from cashier_app.utils.employees_users import validate_username, validate_email, validate_new_password

    

    ok = False
    while not ok:
        username = click.prompt('Username')
        ok, errors = validate_username(username)
        if not ok:
            click.echo(f'Invalid username: {"; ".join(errors)}', err=True)
    
    ok = False
    while not ok:
        email = click.prompt('Email')
        ok, errors = validate_email(email)
        if not ok:
            click.echo(f'Invalid email: {"; ".join(errors)}', err=True)
    
    ok = False
    while not ok:
        password_raw = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        ok, errors = validate_new_password(password_raw)
        if not ok:
            click.echo(f'Invalid password: {"; ".join(errors)}', err=True)

    password_hasher = PasswordHasher(**current_app.config['PASSWORD_HASHER_PARAMETERS'])
    password_hash = password_hasher.hash(password_raw)

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    INSERT INTO employees (username, email, password_hash, is_admin)
                    VALUES (%s, %s, %s, TRUE)
                    ''',
                    (username.strip(), email.strip().lower(), password_hash),
                )
    except IntegrityError as e:
        msg = str(e)
        if 'unique_index_employees_username_active' in msg:
            click.echo('Error: username already taken.', err=True)
        elif 'unique_index_employees_email_active' in msg:
            click.echo('Error: email already taken.', err=True)
        else:
            click.echo(f'Database error: {e}', err=True)
        raise SystemExit(1)

    click.echo(f'Admin employee "{username}" created successfully.')


def backup_db():
    """Vytvoří zálohu databáze pomocí pg_dump.

    Uloží komprimovaný dump (custom formát) do adresáře BACKUP_DIR
    (výchozí: instance/backups) s názvem ve formátu backup_YYYY-MM-DD_HHMMSS.dump.
    Po vytvoření zálohy odstraní staré zálohy nad limit BACKUP_MAX_COUNT.

    Vrátí
    ------
    str
        Absolutní cesta k vytvořenému záložnímu souboru.

    Vyvolá
    ------
    RuntimeError
        Pokud pg_dump skončí s chybou.
    """
    conninfo = current_app.config.get('DATABASE_CONNINFO')
    backup_dir = current_app.config.get(
        'BACKUP_DIR',
        os.path.join(current_app.instance_path, 'backups'),
    )
    max_count = current_app.config.get('BACKUP_MAX_COUNT', 10)

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')
    filename = f'backup_{timestamp}.dump'
    filepath = os.path.join(backup_dir, filename)

    result = subprocess.run(
        ['pg_dump', '--dbname', conninfo, '-Fc', '-f', filepath],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # smaž případný prázdný/neúplný soubor
        if os.path.exists(filepath):
            os.remove(filepath)
        raise RuntimeError(f"pg_dump selhal (kód {result.returncode}): {result.stderr}")

    logger.info("Záloha databáze vytvořena: %s", filepath)

    # rotace: odstraň nejstarší zálohy nad limit
    _rotate_backups(backup_dir, max_count)

    return filepath


def _rotate_backups(backup_dir: str, max_count: int):
    """Odstraní nejstarší záložní soubory, pokud jejich počet překročí max_count.

    Parametry
    ---------
    backup_dir : str
        Adresář se zálohami.
    max_count : int
        Maximální počet záložních souborů, které se mají ponechat.
    """
    backups = sorted(
        (
            f for f in os.listdir(backup_dir)
            if f.startswith('backup_') and f.endswith('.dump')
        ),
    )

    while len(backups) > max_count:
        oldest = backups.pop(0)
        path = os.path.join(backup_dir, oldest)
        os.remove(path)
        logger.info("Stará záloha odstraněna: %s", path)


def get_latest_backup() -> str:
    """Vrátí cestu k nejnovějšímu záložnímu souboru.

    Vrátí
    ------
    str
        Absolutní cesta k nejnovějšímu záložnímu souboru.

    Vyvolá
    ------
    FileNotFoundError
        Pokud žádná záloha neexistuje.
    """
    backup_dir = current_app.config.get(
        'BACKUP_DIR',
        os.path.join(current_app.instance_path, 'backups'),
    )

    if not os.path.isdir(backup_dir):
        raise FileNotFoundError(f"Adresář se zálohami neexistuje: {backup_dir}")

    backups = sorted(
        f for f in os.listdir(backup_dir)
        if f.startswith('backup_') and f.endswith('.dump')
    )

    if not backups:
        raise FileNotFoundError(f"Žádná záloha nenalezena v: {backup_dir}")

    return os.path.join(backup_dir, backups[-1])


def restore_db(filepath: str | None = None):
    """Obnoví databázi ze záložního souboru (custom formát) pomocí pg_restore.

    Parametry
    ---------
    filepath : str | None
        Cesta k záložnímu .dump souboru. Pokud není zadána, použije se
        nejnovější záloha z BACKUP_DIR.

    Vyvolá
    ------
    FileNotFoundError
        Pokud záložní soubor neexistuje.
    RuntimeError
        Pokud pg_restore skončí s chybou.
    """
    if filepath is None:
        filepath = get_latest_backup()

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Záložní soubor nenalezen: {filepath}")

    conninfo = current_app.config.get('DATABASE_CONNINFO')

    result = subprocess.run(
        [
            'pg_restore',
            '--dbname', conninfo,
            '--clean',
            '--if-exists',
            '--single-transaction',
            '--exit-on-error',
            filepath,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"pg_restore selhal (kód {result.returncode}): {result.stderr}")

    logger.info("Databáze obnovena ze zálohy: %s", filepath)
    return filepath


@click.command('backup-db')  # flask --app cashier_app backup-db
@with_appcontext
def backup_db_command():
    """CLI příkaz pro vytvoření zálohy databáze.

    Registruje se jako ``flask --app cashier_app backup-db``.
    """
    try:
        filepath = backup_db()
        click.echo(f'Záloha databáze vytvořena: {filepath}')
    except RuntimeError as e:
        click.echo(f'Chyba při zálohování: {e}', err=True)
        raise SystemExit(1)


@click.command('restore-db')  # flask --app cashier_app restore-db [soubor]
@click.argument('filepath', required=False, default=None)
@with_appcontext
def restore_db_command(filepath):
    """CLI příkaz pro obnovu databáze ze záložního souboru.

    Pokud není zadán soubor, obnoví se z nejnovější zálohy.
    Registruje se jako ``flask --app cashier_app restore-db [soubor]``.
    """
    try:
        restored = restore_db(filepath)
        click.echo(f'Databáze obnovena ze zálohy: {restored}')
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)
    except RuntimeError as e:
        click.echo(f'Chyba při obnově: {e}', err=True)
        raise SystemExit(1)


from flask import Flask
def init_app(app: Flask):
    """Inicializuje fond připojení k databázi a zaregistruje CLI příkazy.

    Vytvoří ConnectionPool na základě konfigurace aplikace, uloží ho
    do ``app.extensions`` a zaregistruje úklidovou funkci při ukončení procesu.
    """
    # app.extensions = getattr(app, "extensions", {})
    conninfo = app.config.get('DATABASE_CONNINFO')

    def _configure_connection(conn):
        """Nastaví časovou zónu UTC pro každé nové fyzické připojení."""
        conn.execute("SET timezone = 'UTC'")
        conn.commit()

    pool = ConnectionPool(
        conninfo,
        kwargs={'row_factory': dict_row},
        min_size=1,
        max_size=5,
        timeout=30,
        configure=_configure_connection,
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
    app.cli.add_command(insert_development_values_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(backup_db_command)
    app.cli.add_command(restore_db_command)