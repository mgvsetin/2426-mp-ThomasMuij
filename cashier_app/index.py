from flask import Blueprint, current_app, jsonify
from cashier_app.events_booths import load_selected_event, load_selected_booth
from cashier_app.db import get_db

bp = Blueprint('order', __name__)

# make it route here if /index
@bp.route('/')
def index():
    return current_app.send_static_file('html/index/index.html')
