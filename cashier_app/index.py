from flask import Blueprint, current_app

bp = Blueprint('index', __name__, url_prefix='/')

@bp.route('')
def get_index_page():
    return current_app.send_static_file('html/index/index.html')


@bp.route('/deleted-users')
def get_deleted_users_page():
    return current_app.send_static_file('html/index/deleted_users.html')