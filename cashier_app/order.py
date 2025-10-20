from flask import Blueprint, current_app, jsonify
from cashier_app.events_booths import load_selected_event, load_selected_booth
from cashier_app.db import get_db

bp = Blueprint('order', __name__)

# make it route here if /index
@bp.route('/')
def index():
    return current_app.send_static_file('index.html')


@bp.route('/get-products')
def get_products():
    booth = load_selected_booth()

    if booth is None:
        return jsonify(error='booth_not_selected'), 403
    
    with get_db() as conn:
        with conn.cursor() as cur:
            products = cur.execute('''
                SELECT products.name, products.description, price.price, images.image_path, images.filename, images.alt_text
                FROM event_product_booth_link as link
                JOIN product_event_prices as price ON link.event_product_id = price.id
                JOIN products ON products.id = price.product_id
                JOIN product_images AS images ON images.product_id = products.id
                WHERE link.booth_id = %s''').fetchall()
            
    if not products:
        return jsonify(success=False, error='products_not_found'), 404
    
    return jsonify(products)