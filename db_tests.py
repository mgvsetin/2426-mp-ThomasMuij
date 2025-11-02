import psycopg
from psycopg.rows import dict_row

from psycopg.types.json import Jsonb

def get_db(row_factory=dict_row, **kwargs):
    conninfo = """
            dbname=cashier_app
            host=localhost
            user=postgres
            password=heslo123
            port=5432"""
    
    return psycopg.connect(conninfo, row_factory=row_factory, **kwargs)


categories = set()
for product in [{'categories': ['Jídlo']}, {'categories': ['Jídlo', 'Hamburger']}]:
    categories.update(product['categories'])

print(categories)

with get_db() as conn:
    with conn.cursor() as cur:
        selectable_categories = cur.execute('''
            SELECT name
            FROM selectable_categories
            WHERE name = ANY(%s::text[])''',
            (list(categories),)).fetchall()
        
print(selectable_categories)