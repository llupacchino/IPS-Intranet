import requests
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

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

def send_status(store_id, terminal_id, status, ip, isp):
    url = "http://54.85.104.167:5000/update"  # Local URL
    try:
        data = {
            "store_id": store_id,
            "terminal_id": terminal_id,
            "status": status,
            "ip": ip,
            "isp": isp
        }
        response = requests.post(url, json=data)
        logging.info(f"Status update response: {response.status_code}")
    except Exception as e:
        logging.error(f"Error: {e}")

def start_terminal(store_id, terminal_id):
    ip, isp = get_ip_info()
    while True:
        send_status(store_id, terminal_id, "connected", ip, isp)
        time.sleep(10)  # Send status updates periodically

if __name__ == "__main__":
    start_terminal('Tarrymore', '1')
