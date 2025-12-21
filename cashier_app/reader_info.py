from flask import Blueprint, jsonify, current_app
from cashier_app.db import get_pool

api_bp = Blueprint('reader_api', __name__, url_prefix='/api/reader')

@api_bp.route('/info')
def reader_info():
    return jsonify(reader_info=current_app.config.get('READER_INFO')), 200


# @bp.route('/booth-is-registered')
# def booth_is_registered():
#     event = load_selected_event()
#     booth = load_selected_booth()

#     # return jsonify(event and booth and event['id'] == booth['event_id']), 200
#     # nejde, protože to může být None
#     if event and booth and event['id'] == booth['event_id']:
#         return jsonify(True), 200
#     else:
#         return jsonify(False), 200