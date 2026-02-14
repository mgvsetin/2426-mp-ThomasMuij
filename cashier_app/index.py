from flask import Blueprint, render_template

bp = Blueprint('index', __name__, url_prefix='/')

@bp.route('')
def get_index_page():
    return render_template('index/index.html')
