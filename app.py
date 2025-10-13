from flask import Flask, request, make_response, jsonify, render_template, redirect, url_for
from markupsafe import escape
from flask_cors import CORS

import sys # remove this line
import print_change # remove this line

app = Flask(__name__)
CORS(app, origins="http://127.0.0.1:5500")

@app.route('/')
def say_hello():
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
        print(request.mimetype)
        print(request.get_data(as_text=True))
        print(request.form)
        print(request.data)
        return 'made a /login POST'
    else:
        print(request.cookies)
        return 'made a /login GET'
    
@app.post('/login/post')
def login_post():
    return 'login successful'

@app.route('/get/static')
def get_static():
    url = app.url_for('static', filename='style.css')
    return url

@app.route('/hello/')
@app.route('/hello/<name>')
def hello(name=None):
    return render_template('hello.html', person=name)


from flask import session

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

@app.route('/session')
def session_index():
    if 'username' in session:
        return f'Logged in as {session["username"]}'
    return 'You are not logged in'

@app.route('/session/login', methods=['GET', 'POST'])
def session_login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect(url_for('session_index'))
    return '''
        <form method="post">
            <p><input type=text name=username>
            <p><input type=submit value=Login>
        </form>
    '''

@app.route('/session/logout')
def session_logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))


from flask import Flask, flash

@app.route('/flash')
def flash_index():
    return render_template('flash_index.html')

@app.route('/flash/login', methods=['GET', 'POST'])
def flash_login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != 'admin' or \
                request.form['password'] != 'secret':
            error = 'Invalid credentials'
        else:
            flash('You were successfully logged in')
            return redirect(url_for('flash_index'))
    return render_template('flash_login.html', error=error)


if __name__ == "__main__":
    app.run(debug=True)