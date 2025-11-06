from cashier_app.db import get_db

def is_manager(employee, event):
    conn = get_db()
    is_manager = False
    with conn.transaction():
        with conn.cursor() as cur:
            is_manager = bool(cur.execute('''
                SELECT 1
                FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s
                AND booth_id IS NULL''',
                (employee['id'], event['id'])).fetchone())
            
    return is_manager
