from flask import Blueprint, current_app


bp = Blueprint('user_manager', __name__, url_prefix='/admin/users')


@bp.route('/manager')
def get_user_manager_page():
    return current_app.send_static_file('html/user_manager/index.html')