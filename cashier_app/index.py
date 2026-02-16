"""Blueprint pro úvodní (hlavní) stránku aplikace."""

from flask import Blueprint, render_template

bp = Blueprint('index', __name__, url_prefix='/')

@bp.route('')
def get_index_page():
    """Vrátí úvodní stránku aplikace."""
    return render_template('index/index.html')
