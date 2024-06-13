import os
import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from threading import Thread
import time
import json
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
socketio = SocketIO(app)

# Dummy credentials
USER_CREDENTIALS = {
    'admin': 'A5348513'
}

# Global dictionaries to store terminal status and expected terminals
expected_terminals = {}
connected_terminals = {}
heartbeat_timeout = 20  # seconds
log_file = 'server_logs.txt'

# Load expected terminals from a file (expected_terminals.json)
def load_expected_terminals():
    global expected_terminals
    try:
        with open('expected_terminals.json') as f:
            expected_terminals = json.load(f)
    except FileNotFoundError:
        print("expected_terminals.json not found")

def combine_terminals(expected, connected):
    combined = {}
    for store, terminals in expected.items():
        for terminal in terminals:
            key = f"{store},{terminal}"
            if key in connected:
                combined[key] = connected[key]
            else:
                combined[key] = {'ip': 'N/A', 'isp': 'N/A', 'status': 'disconnected', 'app_status': 'Not running', 'memory_usage': 'N/A'}
    for key, value in connected.items():
        if key not in combined:
            combined[key] = value
    return combined

def monitor_heartbeats():
    while True:
        current_time = time.time()
        for key, info in list(connected_terminals.items()):
            if current_time - info['last_heartbeat'] > heartbeat_timeout:
                if info['status'] != 'disconnected':
                    connected_terminals[key]['status'] = 'disconnected'
                    logging.info(f"Terminal {key} marked as disconnected")
                    combined_terminals = combine_terminals(expected_terminals, connected_terminals)
                    socketio.emit('update_status', combined_terminals)
        time.sleep(heartbeat_timeout)

def authenticate(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('status'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            session['logged_in'] = True
            return redirect(url_for('status'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/status')
@authenticate
def status():
    combined_terminals = combine_terminals(expected_terminals, connected_terminals)
    return render_template('index.html', combined_terminals=combined_terminals)

@app.route('/api/status', methods=['GET'])
@authenticate
def get_status():
    combined_terminals = combine_terminals(expected_terminals, connected_terminals)
    return jsonify(combined_terminals)

@app.route('/update', methods=['POST'])
def update_status():
    data = request.json
    store_id = data.get('store_id')
    terminal_id = data.get('terminal_id')
    status = data.get('status')
    ip = data.get('ip')
    isp = data.get('isp')
    app_status = data.get('app_status', 'Not running')  # Default to 'Not running' if the key is missing
    memory_usage = data.get('memory_usage', 'N/A')
    key = f"{store_id},{terminal_id}"
    connected_terminals[key] = {
        'ip': ip,
        'isp': isp,
        'status': status,
        'last_heartbeat': time.time(),
        'app_status': app_status,
        'memory_usage': memory_usage
    }
    combined_terminals = combine_terminals(expected_terminals, connected_terminals)
    socketio.emit('update_status', combined_terminals)
    return jsonify({"message": "Status updated"}), 200

@app.route('/log', methods=['POST'])
def save_log():
    data = request.json
    store_id = data.get('store_id')
    terminal_id = data.get('terminal_id')
    log_entry = data.get('log_entry')
    with open(log_file, 'a') as log:
        log.write(f"Store: {store_id}, Terminal: {terminal_id} - {log_entry}")
    return jsonify({"message": "Log saved"}), 200

@app.route('/logs', methods=['GET'])
@authenticate
def get_logs():
    with open(log_file, 'r') as log:
        logs = log.readlines()
    return jsonify(logs)

@app.route('/load_expected_terminals', methods=['POST'])
@authenticate
def load_expected_terminals_api():
    global expected_terminals
    expected_terminals = request.json
    return jsonify(success=True)

@socketio.on('connect')
@authenticate
def handle_connect():
    emit('update_status', combine_terminals(expected_terminals, connected_terminals))

@socketio.on('reboot_terminal')
@authenticate
def handle_reboot_terminal(data):
    store_id, terminal_id = data.split(',')
    logging.info(f"Received reboot command for {store_id}-{terminal_id}")
    emit('reboot_command', {'store_id': store_id, 'terminal_id': terminal_id}, broadcast=True)

@socketio.on('perform_speedtest')
@authenticate
def handle_perform_speedtest(data):
    store_id, terminal_id = data.split(',')
    logging.info(f"Received speedtest command for {store_id}-{terminal_id}")
    emit('speedtest_command', {'store_id': store_id, 'terminal_id': terminal_id}, broadcast=True)

@socketio.on('speedtest_results')
def handle_speedtest_results(data):
    logging.info(f"Received speedtest results: {data}")
    socketio.emit('speedtest_results', data)

if __name__ == '__main__':
    load_expected_terminals()
    heartbeat_thread = Thread(target=monitor_heartbeats)
    heartbeat_thread.start()
    socketio.run(app, host='0.0.0.0', port=80)
    heartbeat_thread.join()
