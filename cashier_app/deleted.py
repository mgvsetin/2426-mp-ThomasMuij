"""Blueprint pro stránky smazaných záznamů (uživatelé a akce)."""

from flask import Blueprint, render_template

bp = Blueprint('deleted', __name__, url_prefix='/deleted')

@bp.route('/users')
def get_deleted_users_page():
    """Vrátí stránku se smazanými uživateli."""
    return render_template('deleted/deleted_users.html')


@bp.route('/events')
def get_deleted_events_page():
    """Vrátí stránku se smazanými akcemi."""
    return render_template('deleted/deleted_events.html')
