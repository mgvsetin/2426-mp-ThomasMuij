import psycopg
from psycopg.rows import dict_row

def get_db(row_factory=dict_row, **kwargs):
    conninfo = """
            dbname=cashier_app
            host=localhost
            user=postgres
            password=heslo123
            port=5432
            options='-c timezone=UTC'"""
    
    return psycopg.connect(conninfo, row_factory=row_factory, **kwargs)

with get_db() as conn:
    with conn.cursor() as cur:
        event_id = cur.execute(f'''
            SELECT event_id
            FROM booths
            WHERE id = %s
            AND deleted_at IS NULL''',
            ("40000000-0000-0000-0000-000000000001",)).fetchone()
        
if not event_id:
    print(event_id)
else:
    event_id = event_id['event_id']
    print(str(event_id) == '30000000-0000-0000-0000-000000000001')


# import sqlite3

# def get_conn():
#     return sqlite3.connect(r'C:\Users\thoma\Documents\code\2426-mp-ThomasMuij\test.sqlite')


# with get_conn() as conn:
#     cur = conn.cursor()

#     print(cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
#     print(cur.execute('SELECT * FROM usr;').fetchall())
#     print(cur.execute('''UPDATE usr
#                       SET age = 15;'''))
#     print(cur.rowcount)
#     print(cur.execute('''UPDATE usr
#                       SET age = 15
#                       WHERE name = "jon";'''))
#     print(cur.rowcount)
#     conn.commit()