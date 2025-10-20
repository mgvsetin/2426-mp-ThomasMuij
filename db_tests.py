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


event_id = "30000000-0000-0000-0000-000000000001"
employee_id = "10000000-0000-0000-0000-000000000002"

with get_db() as conn:
    with conn.cursor() as cur:
        role = cur.execute('''
            SELECT role
            FROM employee_event_booth_roles
            WHERE employee_id = %s
            AND event_id = %s
            AND booth_id IS NULL''',
            (employee_id, event_id)).fetchone()
        
print(role)