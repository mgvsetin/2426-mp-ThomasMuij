"""Blueprint pro API endpoint poskytující informace o čtečce."""

from flask import Blueprint, jsonify, current_app, url_for
from cashier_app.auth import load_logged_in_employee

api_bp = Blueprint('reader_api', __name__, url_prefix='/api/reader')

@api_bp.route('/info')
def reader_info():
    """Vrátí informace o čtečce jako JSON; vyžaduje přihlášeného zaměstnance."""
    logged_employee = load_logged_in_employee()

    if logged_employee is None:
        return jsonify(redirect_url=url_for('auth.get_login_page')), 401

    return jsonify(reader_info=current_app.config.get('READER_INFO')), 200
