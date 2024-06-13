from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

app = Flask(__name__)
socketio = SocketIO(app)

# Global dictionary to store terminal status and last heartbeat time
terminals = {}
heartbeat_timeout = 20  # seconds

@app.route('/status', methods=['GET'])
def get_status():
    global terminals
    # Convert tuple keys to string for JSON serialization
    serializable_terminals = {f"{store},{terminal}": status for (store, terminal), status in terminals.items()}
    return jsonify(serializable_terminals)

@app.route('/update', methods=['POST'])
def update_status():
    data = request.json
    store_id = data['store_id']
    terminal_id = data['terminal_id']
    status = data['status']
    ip = data['ip']
    isp = data['isp']
    terminals[(store_id, terminal_id)] = {'status': status, 'last_heartbeat': time.time(), 'ip': ip, 'isp': isp}
    logging.info(f"Updated status for {store_id}-{terminal_id}: {status}, IP: {ip}, ISP: {isp}")
    socketio.emit('update_status', {'store_id': store_id, 'terminal_id': terminal_id, 'status': status, 'ip': ip, 'isp': isp})
    return jsonify({"message": "Status updated"}), 200

def monitor_heartbeats():
    global terminals
    while True:
        current_time = time.time()
        for (store, terminal), info in list(terminals.items()):
            if current_time - info['last_heartbeat'] > heartbeat_timeout:
                if info['status'] != 'disconnected':
                    terminals[(store, terminal)] = {'status': 'disconnected', 'last_heartbeat': info['last_heartbeat'], 'ip': info['ip'], 'isp': info['isp']}
                    logging.info(f"Terminal {store}-{terminal} marked as disconnected")
                    socketio.emit('update_status', {'store_id': store, 'terminal_id': terminal, 'status': 'disconnected', 'ip': info['ip'], 'isp': info['isp']})
        time.sleep(heartbeat_timeout)

def start_http_server():
    threading.Thread(target=monitor_heartbeats, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    start_http_server()
