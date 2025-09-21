import psycopg
from psycopg.rows import namedtuple_row

def get_connection(conninfo=None, autocommit=True, row_factory=namedtuple_row, **kwargs):
    if conninfo is None:
        return psycopg.connect(
            dbname="cashier_system",
            host="localhost",
            user="postgres",
            password="heslo123",
            port="5432",
            autocommit=autocommit,
            row_factory=row_factory,
            **kwargs)
    else:
        return psycopg.connect(conninfo, autocommit=autocommit, row_factory=row_factory, **kwargs)
