from flask import Flask, request, make_response, jsonify
from markupsafe import escape
from flask_cors import CORS

import sys # remove this line
import print_change # remove this line

app = Flask(__name__)
CORS(app, origins="http://127.0.0.1:5500")

@app.route('/')
def hello():
    return 'hello'

@app.route('/user/<username>')
def show_user_profile(username):
    # show the user profile for that user
    return f'User {escape(username)}'

@app.route('/post/<int:post_id>')
def show_post(post_id):
    # show the post with the given id, the id is an integer
    return f'Post {post_id}'

@app.route('/path/<path:subpath>')
def show_subpath(subpath):
    # show the subpath after /path/
    return f'Subpath {escape(subpath)}'

@app.route('/projects/')
def projects():
    return 'The project page'

@app.route('/about')
def about():
    return 'The about page' + app.url_for('show_user_profile', username='myname') + '|' + str(request.args.getlist('name'))

@app.route('/products')
def get_products():
    response = make_response(jsonify([
        {
    'id': "e43638ce-6aa0-4b85-b27f-e1d07eb678c6",
    'image': "images/products/athletic-cotton-socks-6-pairs.jpg",
    'name': "Black and Gray Athletic Cotton Socks - 6 Pairs",
    'rating': {
      'stars': 4.5,
      'count': 87
    },
    'priceCents': 1090,
    'keywords': [
      "socks",
      "sports",
      "apparel"
    ]
  }
    ]))
    # response.headers.update({
    #     "Access-Control-Allow-Origin": "http://127.0.0.1:5500",
    #     "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    #     "Access-Control-Allow-Headers": "Content-Type, Authorization"
    # })
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # sys.stdout.clear()
        print(request.content_type)
        print(request.get_data(as_text=True))
        return 'made a /login POST'
    else:
        return 'made a /login GET'

if __name__ == "__main__":
    app.run(debug=True)