from flask import Blueprint, jsonify, current_app
from cashier_app.db import get_pool

api_bp = Blueprint('reader_api', __name__, url_prefix='/api/reader')

@api_bp.route('/info')
def reader_info():
    return jsonify(reader_info=current_app.config.get('READER_INFO')), 200
