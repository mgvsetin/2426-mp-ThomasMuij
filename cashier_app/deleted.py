from flask import Blueprint, current_app

bp = Blueprint('deleted', __name__, url_prefix='/deleted')

@bp.route('/users')
def get_deleted_users_page():
    return current_app.send_static_file('html/deleted/deleted_users.html')


@bp.route('/events')
def get_deleted_events_page():
    return current_app.send_static_file('html/deleted/deleted_events.html')
