import requests
import time
import logging
import psutil
import socketio
import os
import speedtest
import sys
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

SERVER_URL = "http://intranet.ipsdash.com"
CONFIG_PATH = 'config.txt'

def read_config(file_path):
    config = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                name, value = line.strip().split('=')
                config[name] = value
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        config['store_id'] = 'Unknown'
        config['terminal_id'] = 'Unknown'
        config['version'] = '0.0'  # Default version if not present
    return config

def write_config(file_path, config):
    try:
        with open(file_path, 'w') as file:
            for key, value in config.items():
                file.write(f"{key}={value}\n")
    except Exception as e:
        logging.error(f"Error writing config file: {e}")

def get_ip_info():
    try:
        response = requests.get("http://ipinfo.io/json")
        data = response.json()
        ip = data.get('ip', 'Unknown')
        isp = data.get('org', 'Unknown')
        return ip, isp
    except Exception as e:
        logging.error(f"Error fetching IP info: {e}")
        return "Unknown", "Unknown"

def is_app_running(app_name):
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == app_name:
            return True
    return False

def get_memory_usage():
    memory = psutil.virtual_memory()
    return memory.percent

def is_windows_locked():
    return is_app_running('LogonUI.exe')

def perform_speedtest():
    try:
        st = speedtest.Speedtest()
        st.download()
        st.upload()
        results = st.results.dict()
        download_speed = results.get('download', 0) / 1_000_000  # Convert to Mbps
        upload_speed = results.get('upload', 0) / 1_000_000      # Convert to Mbps
        return download_speed, upload_speed
    except Exception as e:
        logging.error(f"Error performing speedtest: {e}")
        return None, None

def log_change(event, details, store_id, terminal_id):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_entry = f"{timestamp} - {event}: {details}\n"
    try:
        response = requests.post(f"{SERVER_URL}/log", json={
            'store_id': store_id,
            'terminal_id': terminal_id,
            'log_entry': log_entry
        })
        if response.status_code != 200:
            logging.error(f"Failed to send log to server: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending log to server: {e}")

def send_status(store_id, terminal_id, status, ip, isp, app_status, memory_usage, logon_status, download_speed=None, upload_speed=None):
    url = f"{SERVER_URL}/update"
    try:
        data = {
            "store_id": store_id,
            "terminal_id": terminal_id,
            "status": status,
            "ip": ip,
            "isp": isp,
            "app_status": app_status,
            "memory_usage": memory_usage,
            "logon_status": logon_status,
            "download_speed": download_speed,
            "upload_speed": upload_speed
        }
        response = requests.post(url, json=data)
        logging.info(f"Status update response: {response.status_code}")
    except Exception as e:
        logging.error(f"Error: {e}")

def check_for_updates(current_version):
    try:
        response = requests.get(f"{SERVER_URL}/check_update")
        data = response.json()
        latest_version = data['version']
        if latest_version != current_version:
            logging.info(f"New version available: {latest_version}")
            return latest_version
    except Exception as e:
        logging.error(f"Error checking for updates: {e}")
    return None

def download_update():
    try:
        response = requests.get(f"{SERVER_URL}/download_update")
        with open('terminal_new.exe', 'wb') as file:
            file.write(response.content)
        logging.info("Update downloaded")
        return True
    except Exception as e:
        logging.error(f"Error downloading update: {e}")
    return False

def apply_update():
    try:
        with open('update_and_relaunch.bat', 'w') as bat_file:
            bat_file.write(f'''
            @echo off
            timeout /t 5 /nobreak > nul
            taskkill /f /im terminal.exe > nul
            move /y "terminal_new.exe" "terminal.exe"
            start /min terminal.exe
            del update_and_relaunch.bat
            ''')
        subprocess.Popen(['update_and_relaunch.bat'], shell=True)
        return True
    except Exception as e:
        logging.error(f"Error applying update: {e}")
    return False

def start_terminal(config):
    ip, isp = get_ip_info()
    app_name = config.get('app_name', 'example.exe')  # Replace 'example.exe' with your actual .exe file name
    current_version = config.get('version', '0.0')
    last_ip = ip
    last_isp = isp
    last_app_status = "Not running"

    sio = socketio.Client()

    @sio.event
    def connect():
        logging.info("Connected to server")
        memory_usage = get_memory_usage()
        logon_status = is_windows_locked()
        send_status(config['store_id'], config['terminal_id'], "connected", ip, isp, "Not running", memory_usage, logon_status)

    @sio.event
    def disconnect():
        logging.info("Disconnected from server")

    @sio.on('reboot_command')
    def on_reboot_command(data):
        if data['store_id'] == config['store_id'] and data['terminal_id'] == config['terminal_id']:
            logging.info(f"Received reboot command for {config['store_id']}-{config['terminal_id']}")
            os.system("shutdown /r /t 1")

    @sio.on('speedtest_command')
    def on_speedtest_command(data):
        if data['store_id'] == config['store_id'] and data['terminal_id'] == config['terminal_id']:
            logging.info(f"Received speedtest command for {config['store_id']}-{config['terminal_id']}")
            download_speed, upload_speed = perform_speedtest()
            speedtest_results = {
                'store_id': config['store_id'],
                'terminal_id': config['terminal_id'],
                'download_speed': download_speed,
                'upload_speed': upload_speed
            }
            sio.emit('speedtest_results', speedtest_results)

    sio.connect(SERVER_URL)

    while True:
        app_status = "Running" if is_app_running(app_name) else "Not running"
        memory_usage = get_memory_usage()
        logon_status = is_windows_locked()

        send_status(config['store_id'], config['terminal_id'], "connected", ip, isp, app_status, memory_usage, logon_status)

        new_version = check_for_updates(current_version)
        if new_version:
            if download_update():
                if apply_update():
                    logging.info("Restarting to apply update")
                    config['version'] = new_version
                    write_config(CONFIG_PATH, config)
                    sys.exit()

        time.sleep(10)  # Send status updates periodically

if __name__ == "__main__":
    config = read_config(CONFIG_PATH)
    start_terminal(config)
