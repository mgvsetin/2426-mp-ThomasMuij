"""Modul pro správu PostgreSQL připojení v kontextu Flask aplikace.


Funkce get_db zajišťuje znovupoužití existujícího spojeni uloženého v `g` pokud
parametry připojení souhlasí, jinak vytvoří nové.
"""

from flask import g, current_app
import click
import psycopg
from psycopg.rows import dict_row
import types


# přemění hodnotu tak, aby se dala provnávat
def _repr_for_metadata(value):
    """Normalizuje hodnoty argumentů při porovnání metadata připojení.


    Vrátí n-tici popisující typ a reprezentaci hodnoty tak, aby bylo možné
    porovnat parametry používané pro vytvóření Connection.
    """
    # callables: reprezentujeme: module_name + qualified_name
    if isinstance(value, types.FunctionType) or callable(value):
        module_name = getattr(value, "__module__", None)
        # jméno funkce/třídy zahrnující nesting (např. "RowFactory.dict_row")
        qualified_name = getattr(value, "__qualname__", getattr(value, "__name__", repr(value)))
        return ("callable", module_name, qualified_name)
    # objekty, které jsou hashable (ints, str, bool, None, tuples,...)
    try:
        hash(value)
        return ("primitive", value)
    except Exception:
        # fallback na repr pro unhashable (např. dicts, lists)
        return ("repr", repr(value))


def _make_metadata(conninfo, kwargs):
    """Vytvoří metadata popisující připojení, které jdou porovnat mezi voláními.


    Parametry
    ---------
    conninfo: str
    Retezec připojení (obsahuje např. dbname, host, user...)
    kwargs: dict
    Dodateční argumenty předávané psycopg.connect (např. row_factory)
    """
    meta = {"conninfo": conninfo}
    for k, v in kwargs.items():
        meta[k] = _repr_for_metadata(v)
    return meta


def get_db(row_factory=dict_row, autocommit=True, **kwargs):
    """Zajistí připojení k databázi uložené v `g` nebo vytvoří nové,
    pokud neexistuje nebo se metadata liší.
    
    
    Parametry
    ---------
    row_factory:
    Továrni funkce pro řádky (default: psycopg.rows.dict_row).
    autocommit: bool
    Zda použít autocommit pro připojení.
    **kwargs:
    Další argumenty předávané do psycopg.connect.
    
    
    Vrátí
    ------
    psycopg.Connection
    Aktivní spojeni k databázi.
    """
    conninfo = current_app.config.get('DATABASE_CONNINFO')

    requested_args = {'row_factory': row_factory,
                      'autocommit': autocommit}
    requested_args.update(kwargs)

    requested_metadata = _make_metadata(conninfo, requested_args)

    conn = g.get('db')
    existing_meta = g.get('db_meta')

    # srovnáme argumenty, s kterým Connection byla vytvořena s novýma
    if conn is None or existing_meta != requested_metadata:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

        g.db = psycopg.connect(conninfo, **requested_args)
        g.db_meta = requested_metadata

        return g.db

    # připojení je zavřené nebo jinak pokažené
    try:
        with conn.cursor():
            pass
    except psycopg.OperationalError:
        try:
            conn.close()
        except Exception:
            pass
        g.db = psycopg.connect(conninfo, **requested_args)
        g.db_meta = requested_metadata

    return g.db # vrátíme původní pokud jde/stejné, jinak nové


def close_db(e=None):
    """Uzavře připojení k databázi uložené v `g`.


    Parametry
    ---------
    e: optional
    Chybový objekt (přijímáno teardown hooky Flasku), nevyužívá se.
    """
    db = g.pop('db', None)
    g.pop('db_meta', None)

    if db is not None:
        db.close()


def init_db():
    """Inicializuje databázi podle souboru schema.sql v instanci aplikace.


    Načte SQL ze souboru schema.sql a vykoná ho přes připojení.
    """
    with current_app.open_resource('schema.sql', 'r', 'utf-8') as f:
        sql = f.read()

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql)


@click.command('init-db') # flask --app cashier_app init-db
def init_db_command():
    """CLI příkaz pro inicializaci databáze.


    Tento příkaz registruje `flask --app cashier_app init-db`.
    """
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    """Připojí teardown handler a CLI příkazy do Flask aplikace.


    Parametry
    ---------
    app: Flask
    Aplikace, ke které se registrují teardown a příkazy.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
