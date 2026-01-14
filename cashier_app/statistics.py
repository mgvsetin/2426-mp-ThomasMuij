from flask import Blueprint, jsonify, url_for
from cashier_app.auth import load_logged_in_employee
from cashier_app.db import get_pool
from cashier_app.employee_events_booths import has_role_event_manager_for_event, has_role_admin


api_bp = Blueprint('event_statistics_api', __name__, url_prefix='/api/events')


@api_bp.route('/<event_id>/statistics', methods=('GET',))
def get_event_statistics(event_id):
    """
    Získá kompletní statistiky pro danou akci.
    Vrací data o:
    - Celkových transakcích
    - Transakcích podle stánků
    - Transakcích podle produktů
    - Časovém rozložení transakcí
    """
    logged_employee = load_logged_in_employee()
    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    try:
        event_id = str(event_id).strip()
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not event_id:
        return jsonify(error='missing_event_id'), 400

    # Kontrola oprávnění
    if not has_role_admin(logged_employee) and not has_role_event_manager_for_event(logged_employee, event_id):
        return jsonify(error='insufficient_priviliges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Kontrola existence akce
            event = cur.execute(
                '''
                SELECT id, name, start_at, end_at, created_at
                FROM events
                WHERE id = %s AND deleted_at IS NULL
                ''',
                (event_id,)
            ).fetchone()

            if not event:
                return jsonify(error='event_not_found'), 404

            # 1. CELKOVÉ STATISTIKY AKCE
            overall_stats = cur.execute(
                '''
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(DISTINCT wallet_id) as unique_wallets,
                    COUNT(DISTINCT user_id) as unique_users,
                    SUM(CASE WHEN transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN transaction_type = 'refund' THEN 1 ELSE 0 END) as refund_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as total_revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as total_deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as total_withdrawals_czk,
                    SUM(CASE WHEN transaction_type = 'refund' THEN amount_czk ELSE 0 END) as total_refunds_czk
                FROM transactions
                WHERE event_id = %s
                ''',
                (event_id,)
            ).fetchone()

            # 2. STATISTIKY PODLE STÁNKŮ
            booth_stats = cur.execute(
                '''
                SELECT 
                    b.id as booth_id,
                    b.name as booth_name,
                    b.booth_type,
                    COUNT(t.id) as transaction_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN 1 ELSE 0 END) as payment_count,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' THEN 1 ELSE 0 END) as balance_change_count,
                    SUM(CASE WHEN t.transaction_type = 'refund' THEN 1 ELSE 0 END) as refund_count,
                    SUM(CASE WHEN t.transaction_type = 'payment' THEN -t.amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk > 0 THEN t.amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN t.transaction_type = 'balance-change' AND t.amount_czk < 0 THEN -t.amount_czk ELSE 0 END) as withdrawals_czk,
                    SUM(CASE WHEN t.transaction_type = 'refund' THEN t.amount_czk ELSE 0 END) as refunds_czk
                FROM booths b
                LEFT JOIN transactions t ON t.booth_id = b.id
                WHERE b.event_id = %s AND b.deleted_at IS NULL
                GROUP BY b.id, b.name, b.booth_type
                ORDER BY revenue_czk DESC NULLS LAST
                ''',
                (event_id,)
            ).fetchall()

            # 3. STATISTIKY PODLE PRODUKTŮ
            # Extrahujeme produkty z products_info JSON pole v transakcích
            product_stats = cur.execute(
                '''
                WITH product_items AS (
                    SELECT 
                        t.id as transaction_id,
                        t.booth_id,
                        t.occurred_at,
                        jsonb_array_elements(t.products_info) as product_item
                    FROM transactions t
                    WHERE t.event_id = %s 
                    AND t.transaction_type = 'payment'
                    AND t.products_info IS NOT NULL
                    AND jsonb_array_length(t.products_info) > 0
                )
                SELECT 
                    product_item->>'name' as product_name,
                    SUM((product_item->>'quantity')::int) as total_quantity,
                    SUM((product_item->>'price')::int * (product_item->>'quantity')::int) as total_revenue_czk,
                    AVG((product_item->>'price')::int) as avg_price_czk,
                    COUNT(DISTINCT transaction_id) as transaction_count,
                    COUNT(DISTINCT booth_id) as booth_count
                FROM product_items
                GROUP BY product_item->>'name'
                ORDER BY total_revenue_czk DESC
                ''',
                (event_id,)
            ).fetchall()

            # 4. ČASOVÉ ROZLOŽENÍ TRANSAKCÍ (po hodinách)
            hourly_stats = cur.execute(
                '''
                SELECT 
                    DATE_TRUNC('hour', occurred_at) as hour,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk
                FROM transactions
                WHERE event_id = %s
                GROUP BY DATE_TRUNC('hour', occurred_at)
                ORDER BY hour ASC
                ''',
                (event_id,)
            ).fetchall()

            # 5. DENNÍ STATISTIKY
            daily_stats = cur.execute(
                '''
                SELECT 
                    DATE_TRUNC('day', occurred_at) as day,
                    COUNT(*) as transaction_count,
                    SUM(CASE WHEN transaction_type = 'payment' THEN -amount_czk ELSE 0 END) as revenue_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk > 0 THEN amount_czk ELSE 0 END) as deposits_czk,
                    SUM(CASE WHEN transaction_type = 'balance-change' AND amount_czk < 0 THEN -amount_czk ELSE 0 END) as withdrawals_czk
                FROM transactions
                WHERE event_id = %s
                GROUP BY DATE_TRUNC('day', occurred_at)
                ORDER BY day ASC
                ''',
                (event_id,)
            ).fetchall()

            # 6. TOP 10 PRODUKTŮ podle tržeb
            top_products = cur.execute(
                '''
                WITH product_items AS (
                    SELECT 
                        jsonb_array_elements(t.products_info) as product_item
                    FROM transactions t
                    WHERE t.event_id = %s 
                    AND t.transaction_type = 'payment'
                    AND t.products_info IS NOT NULL
                    AND jsonb_array_length(t.products_info) > 0
                )
                SELECT 
                    product_item->>'name' as product_name,
                    SUM((product_item->>'quantity')::int) as total_quantity,
                    SUM((product_item->>'price')::int * (product_item->>'quantity')::int) as total_revenue_czk
                FROM product_items
                GROUP BY product_item->>'name'
                ORDER BY total_revenue_czk DESC
                LIMIT 10
                ''',
                (event_id,)
            ).fetchall()

            # 7. STATISTIKY O PENĚŽENKÁCH
            wallet_stats = cur.execute(
                '''
                SELECT 
                    COUNT(*) as total_wallets,
                    SUM(balance_czk) as total_balance_czk,
                    AVG(balance_czk) as avg_balance_czk,
                    MAX(balance_czk) as max_balance_czk,
                    MIN(balance_czk) as min_balance_czk
                FROM wallets
                WHERE event_id = %s AND deleted_at IS NULL
                ''',
                (event_id,)
            ).fetchone()

    return jsonify(
        event={
            'id': event['id'],
            'name': event['name'],
            'start_at': event['start_at'].isoformat() if event['start_at'] else None,
            'end_at': event['end_at'].isoformat() if event['end_at'] else None,
            'created_at': event['created_at'].isoformat() if event['created_at'] else None
        },
        overall_statistics={
            'total_transactions': overall_stats['total_transactions'] or 0,
            'unique_wallets': overall_stats['unique_wallets'] or 0,
            'unique_users': overall_stats['unique_users'] or 0,
            'payment_count': overall_stats['payment_count'] or 0,
            'balance_change_count': overall_stats['balance_change_count'] or 0,
            'refund_count': overall_stats['refund_count'] or 0,
            'total_revenue_czk': overall_stats['total_revenue_czk'] or 0,
            'total_deposits_czk': overall_stats['total_deposits_czk'] or 0,
            'total_withdrawals_czk': overall_stats['total_withdrawals_czk'] or 0,
            'total_refunds_czk': overall_stats['total_refunds_czk'] or 0
        },
        booth_statistics=[{
            'booth_id': b['booth_id'],
            'booth_name': b['booth_name'],
            'booth_type': b['booth_type'],
            'transaction_count': b['transaction_count'] or 0,
            'payment_count': b['payment_count'] or 0,
            'balance_change_count': b['balance_change_count'] or 0,
            'refund_count': b['refund_count'] or 0,
            'revenue_czk': b['revenue_czk'] or 0,
            'deposits_czk': b['deposits_czk'] or 0,
            'withdrawals_czk': b['withdrawals_czk'] or 0,
            'refunds_czk': b['refunds_czk'] or 0
        } for b in booth_stats],
        product_statistics=[{
            'product_name': p['product_name'],
            'total_quantity': p['total_quantity'] or 0,
            'total_revenue_czk': p['total_revenue_czk'] or 0,
            'avg_price_czk': float(p['avg_price_czk']) if p['avg_price_czk'] else 0,
            'transaction_count': p['transaction_count'] or 0,
            'booth_count': p['booth_count'] or 0
        } for p in product_stats],
        top_products=[{
            'product_name': p['product_name'],
            'total_quantity': p['total_quantity'] or 0,
            'total_revenue_czk': p['total_revenue_czk'] or 0
        } for p in top_products],
        hourly_statistics=[{
            'hour': h['hour'].isoformat() if h['hour'] else None,
            'transaction_count': h['transaction_count'] or 0,
            'revenue_czk': h['revenue_czk'] or 0,
            'deposits_czk': h['deposits_czk'] or 0
        } for h in hourly_stats],
        daily_statistics=[{
            'day': d['day'].isoformat() if d['day'] else None,
            'transaction_count': d['transaction_count'] or 0,
            'revenue_czk': d['revenue_czk'] or 0,
            'deposits_czk': d['deposits_czk'] or 0,
            'withdrawals_czk': d['withdrawals_czk'] or 0
        } for d in daily_stats],
        wallet_statistics={
            'total_wallets': wallet_stats['total_wallets'] or 0,
            'total_balance_czk': wallet_stats['total_balance_czk'] or 0,
            'avg_balance_czk': float(wallet_stats['avg_balance_czk']) if wallet_stats['avg_balance_czk'] else 0,
            'max_balance_czk': wallet_stats['max_balance_czk'] or 0,
            'min_balance_czk': wallet_stats['min_balance_czk'] or 0
        }
    ), 200