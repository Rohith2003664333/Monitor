from pymongo import MongoClient
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import threading
import time
import os
import requests

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # Replace with a secure key

# Connect to MongoDB
client = MongoClient("mongodb+srv://rh0665971:q7DFaWad4RKQRiWg@cluster0.gusg4.mongodb.net/?retryWrites=true&w=majority")
db = client["monitor"]
users_collection = db["users"]

# In-memory store for tweak threads
tweak_threads = {}

# Function to tweak website
def tweak_website(username):
    while True:
        user = users_collection.find_one({'username': username})
        if not user or user.get('tweak_status') != 'running':
            break
        
        website = user.get('website')
        if not website:
            break
            
        try:
            # Fetch the website content
            response = requests.get(website)
            html_content = response.text

            # Perform tweaks (example: replace 'example' with 'sample')
            tweaked_content = html_content.replace('example', 'sample')

            # Log tweaked content or perform further processing
            print(f"Tweaked content for {username}: {tweaked_content[:100]}...")  # For demonstration

            # Update last tweak time
            users_collection.update_one({'username': username}, {'$set': {'last_tweak_time': time.time()}})
        except Exception as e:
            print(f"Error tweaking website for {username}: {e}")

        # Wait for 2 minutes
        time.sleep(30)

# Decorator to require login for certain routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Route for the root URL
@app.route('/', methods=['GET'])
def home():
    if 'username' in session:
        return redirect(url_for('index'))  # Redirect to the index page if already logged in
    return redirect(url_for('login_page'))  # Otherwise, redirect to the login page

# Route to serve login page
@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

# Route to handle login
@app.route('/login', methods=['POST'])
def login():
    data = request.form
    username = data.get('username')
    password = data.get('password')

    user = users_collection.find_one({'username': username})
    if user and check_password_hash(user['password'], password):
        session['username'] = username
        return redirect(url_for('index'))
    else:
        return render_template('login.html', error='Invalid credentials!')

# Route to serve registration page
@app.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')

# Route to handle registration
@app.route('/register', methods=['POST'])
def register():
    data = request.form
    username = data.get('username')
    password = data.get('password')

    if users_collection.find_one({'username': username}):
        return render_template('register.html', error='User already exists!')
    
    hashed_password = generate_password_hash(password)
    users_collection.insert_one({
        'username': username,
        'password': hashed_password,
        'tweak_status': 'paused',
        'website': '',
        'last_tweak_time': None
    })
    return redirect(url_for('login_page'))

# Route to serve index page (protected)
@app.route('/index', methods=['GET'])
@login_required
def index():
    user = users_collection.find_one({'username': session['username']})
    return render_template('index.html', username=session['username'], website=user.get('website', ''))

# API to update website link and start tweaking
@app.route('/update_link', methods=['POST'])
@login_required
def update_link():
    data = request.form
    username = session['username']
    website = data.get('website')

    if not website.startswith('https://'):
        return jsonify({'message': 'Invalid URL format! Must start with https://'}), 400

    # Update the website link and set tweak_status to 'running'
    users_collection.update_one({'username': username}, {'$set': {'website': website, 'tweak_status': 'running'}})

    # Start tweaking thread if not already running
    if username not in tweak_threads or not tweak_threads[username].is_alive():
        thread = threading.Thread(target=tweak_website, args=(username,))
        thread.start()
        tweak_threads[username] = thread

    return jsonify({'message': 'Website link updated! Tweaking started.'}), 200

# API to pause tweaking
@app.route('/pause_tweaking', methods=['POST'])
@login_required
def pause_tweaking():
    username = session['username']

    # Update tweak_status to 'paused'
    users_collection.update_one({'username': username}, {'$set': {'tweak_status': 'paused'}})

    return jsonify({'message': 'Tweaking paused!'}), 200

# API to resume tweaking
@app.route('/resume_tweaking', methods=['POST'])
@login_required
def resume_tweaking():
    username = session['username']

    # Get user's website
    user = users_collection.find_one({'username': username})
    website = user.get('website')

    if not website:
        return jsonify({'message': 'No website link found!'}), 400

    # Update tweak_status to 'running'
    users_collection.update_one({'username': username}, {'$set': {'tweak_status': 'running'}})

    # Start tweaking thread if not already running
    if username not in tweak_threads or not tweak_threads[username].is_alive():
        thread = threading.Thread(target=tweak_website, args=(username,))
        thread.start()
        tweak_threads[username] = thread

    return jsonify({'message': 'Tweaking resumed!'}), 200

# Route to logout
@app.route('/logout', methods=['GET'])
@login_required
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

if __name__ == "__main__":
    app.run(debug=True)
