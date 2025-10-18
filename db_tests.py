import psycopg
from psycopg.rows import dict_row

def get_db(row_factory=dict_row, **kwargs):
    conninfo = """
            dbname=cashier_app
            host=localhost
            user=postgres
            password=heslo123
            port=5432"""
    
    return psycopg.connect(conninfo, row_factory=row_factory, **kwargs)


with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute(
            '''
            SELECT role
            FROM account_event_roles
            WHERE account_id = %s''',
            ('6623c93b-0612-4811-ae98-aad8817ecb73',))
        cur.execute(
            '''
            SELECT role
            FROM account_event_roles
            WHERE account_id = %s''',
            ('6623c93b-0612-4811-ae98-aad8817ecb72',))
        role = cur.fetchone()['role']
        
print(role)