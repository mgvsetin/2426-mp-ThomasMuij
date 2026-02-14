from flask import Blueprint, render_template

bp = Blueprint('deleted', __name__, url_prefix='/deleted')

@bp.route('/users')
def get_deleted_users_page():
    return render_template('deleted/deleted_users.html')


@bp.route('/events')
def get_deleted_events_page():
    return render_template('deleted/deleted_events.html')
