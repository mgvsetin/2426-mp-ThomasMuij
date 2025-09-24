import psycopg
from psycopg.rows import namedtuple_row

def get_connection(autocommit=True, row_factory=namedtuple_row, **kwargs):
    conninfo = """
        dbname=cashier_system,
        host=localhost,
        user=postgres,
        password=heslo123,
        port=5432"""
        
    return psycopg.connect(conninfo, autocommit=autocommit, row_factory=row_factory, **kwargs)
