"""Modul pro CSV exporty (účetnictví): plný přehled transakcí a nevyčerpané zůstatky peněženek."""

import csv
import io
from flask import Blueprint, Response, g, jsonify
from cashier_app.auth import require_login
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager

api_exports_bp = Blueprint('exports_api', __name__)


def _format_products(products_info):
    """Vytvoří lidsky čitelný souhrn produktů ve formátu '2x Pivo (50 Kč), 1x Párek (80 Kč)'."""
    if not products_info:
        return ''
    return ', '.join(
        f"{p.get('quantity', 1)}x {p.get('name', '')} ({p.get('price', 0)} Kč)"
        for p in products_info
    )


@api_exports_bp.route('/<uuid:event_id>/transactions/csv')
@require_login
def export_transactions_csv(event_id):
    """Plný přehled transakcí pro danou akci jako CSV (pro účetnictví)."""
    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            transactions = cur.execute(
                '''
                SELECT t.id, t.tag_id, t.transaction_type, t.amount_czk, t.balance_before, t.balance_after, t.occurred_at, t.products_info,
                       e.username AS performed_by_username,
                       u.first_name AS user_first_name, u.last_name AS user_last_name,
                       b.name AS booth_name,
                       EXISTS (SELECT 1 FROM transactions r WHERE r.refunded_transaction_id = t.id) AS is_refunded
                FROM transactions t
                JOIN employees e ON e.id = t.performed_by
                JOIN booths b ON b.id = t.booth_id
                LEFT JOIN users u ON u.id = t.user_id
                WHERE t.event_id = %s
                ORDER BY t.occurred_at, t.id
                ''',
                (event_id,)
            ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['id', 'occurred_at', 'transaction_type', 'amount_czk', 'balance_before', 'balance_after',
                     'tag_id', 'user_first_name', 'user_last_name', 'booth_name', 'performed_by_username',
                     'is_refunded', 'products'])
    for t in transactions:
        writer.writerow([
            t['id'], t['occurred_at'].isoformat(), t['transaction_type'], t['amount_czk'],
            t['balance_before'], t['balance_after'], t['tag_id'],
            t['user_first_name'] or '', t['user_last_name'] or '', t['booth_name'],
            t['performed_by_username'], t['is_refunded'], _format_products(t['products_info']),
        ])

    # Content-Disposition, attachment -> soubor pro stáhnutí
    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="transactions_{event_id}.csv"'}
    )


@api_exports_bp.route('/<uuid:event_id>/unredeemed-wallets/csv')
@require_login
def export_unredeemed_wallets_csv(event_id):
    """Peněženky s nenulovým kladným zůstatkem pro danou akci jako CSV (závazek vůči návštěvníkům)."""
    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            wallets = cur.execute(
                '''
                SELECT w.id, w.tag_id, w.balance_czk,
                       u.first_name, u.last_name, u.email, u.phone_number, u.other_identifier
                FROM wallets w
                LEFT JOIN users u ON u.id = w.owner_id
                WHERE w.event_id = %s
                  AND w.balance_czk > 0
                ORDER BY w.balance_czk DESC, u.last_name, u.first_name
                ''',
                (event_id,)
            ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['wallet_id', 'tag_id', 'balance_czk',
                     'owner_first_name', 'owner_last_name', 'owner_email', 'owner_phone', 'owner_other_identifier'])
    for w in wallets:
        writer.writerow([
            w['id'], w['tag_id'], w['balance_czk'],
            w['first_name'] or '', w['last_name'] or '',
            w['email'] or '', w['phone_number'] or '', w['other_identifier'] or '',
        ])

    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="unredeemed_wallets_{event_id}.csv"'}
    )
