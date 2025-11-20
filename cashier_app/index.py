from flask import Blueprint, current_app

bp = Blueprint('order', __name__)

# make it route here if /index
@bp.route('/')
def index():
    return current_app.send_static_file('html/index/index.html')
