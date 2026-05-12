"""Modul pro historii transakcí událostí a uživatelů."""

from flask import Blueprint, g, jsonify, url_for, render_template
from uuid import UUID
from cashier_app.auth import load_logged_in_employee, require_login
from cashier_app.employee_events_booths import load_selected_event, load_selected_booth
from cashier_app.db import get_pool
from cashier_app.utils.employees_users import is_manager

bp = Blueprint('transaction_history', __name__, url_prefix='/events')


@bp.route('/<uuid:event_id>/users/<uuid:user_id>/transaction-history')
def get_user_transaction_history_page(event_id, user_id):
    """Vrátí stránku s historií transakcí konkrétního uživatele pro danou událost."""
    return render_template('transaction_history/user_transaction_history.html')


@bp.route('/<uuid:event_id>/transaction-history')
def get_event_transaction_history_page(event_id):
    """Vrátí stránku s historií všech transakcí pro danou událost."""
    return render_template('transaction_history/event_transaction_history.html')


api_transaction_history_bp = Blueprint('transaction_history_api', __name__)


@api_transaction_history_bp.route('/<uuid:event_id>/users/<uuid:user_id>/transaction-history')
@require_login
def get_user_transaction_history_for_event(event_id, user_id):
    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(str(event_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not user_id:
        return jsonify(error='missing_user_id'), 400

    try:
        user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_user_id'), 400

    can_admin_refund = g.employee['is_admin'] or bool(is_manager(g.employee['id'], event_id))

    if not can_admin_refund:
        selected_event = load_selected_event()
        if not selected_event or selected_event['id'] != event_id:
            return jsonify(error='insufficient_privileges'), 403

        selected_booth = load_selected_booth()

        if not selected_booth or selected_booth['booth_type'] != 'cashier':
            return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            user_transaction_history = cur.execute(
                '''
                SELECT t.id, t.tag_id, t.transaction_type, t.amount_czk, t.balance_before, t.balance_after, t.occurred_at, t.products_info,
                       e.username AS performed_by_username, b.name AS booth_name,
                       EXISTS (SELECT 1 FROM transactions r WHERE r.refunded_transaction_id = t.id) AS is_refunded
                FROM transactions t
                JOIN users u ON u.id = t.user_id
                JOIN employees e ON e.id = t.performed_by
                JOIN booths b ON b.id = t.booth_id
                WHERE t.user_id = %s
                AND t.event_id = %s
                ORDER BY t.occurred_at, t.id
                ''',
                (user_id, event_id)).fetchall()

    return jsonify(user_transaction_history=user_transaction_history, can_admin_refund=can_admin_refund), 200


@api_transaction_history_bp.route('/<uuid:event_id>/transaction-history')
@require_login
def get_event_transaction_history(event_id):
    if not event_id:
        return jsonify(error='missing_event_id'), 400

    try:
        event_id = UUID(str(event_id))
    except (TypeError, ValueError):
        return jsonify(error='invalid_event_id'), 400

    if not g.employee['is_admin'] and not is_manager(g.employee['id'], event_id):
        return jsonify(error='insufficient_privileges'), 403

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            event_transaction_history = cur.execute(
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
                (event_id,)).fetchall()

    return jsonify(event_transaction_history=event_transaction_history, can_admin_refund=True), 200
