import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer
import socketio
import requests
import json

class TerminalStatusApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPS Intranet - Terminal Status")
        self.setGeometry(100, 100, 1000, 700)

        # Set up the main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Create the tree widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Store", "Terminal", "IP", "ISP"])
        self.layout.addWidget(self.tree)

        # Set up SocketIO client
        self.sio = socketio.Client()
        self.sio.on('update_status', self.on_update_status)
        self.sio.connect("http://54.85.104.167:5000")  # Updated to public server IP

        self.load_expected_terminals()
        self.update_status()

        # Set up a timer to update the status every 5 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)

    def load_expected_terminals(self):
        with open('expected_terminals.json') as f:
            self.expected_terminals = json.load(f)

    def on_update_status(self, data):
        self.update_tree()

    def update_tree(self):
        try:
            response = requests.get("http://54.85.104.167:5000/status")  # Updated to public server IP
            if response.status_code == 200:
                connected_terminals = response.json()
            else:
                print(f"Error fetching status: {response.status_code}")
                connected_terminals = {}
        except Exception as e:
            print(f"Error fetching status: {e}")
            connected_terminals = {}

        self.tree.clear()

        # Add connected terminals
        for key, info in connected_terminals.items():
            store, terminal = key.split(',')
            ip = info['ip']
            isp = info['isp']
            status = info['status']
            color = 'green' if status == 'connected' else 'red'
            item = QTreeWidgetItem([store, terminal, ip, isp])
            if status == 'connected':
                item.setBackground(0, QColor(144, 238, 144))  # Light green background
            else:
                item.setBackground(0, QColor(240, 128, 128))  # Light coral background
            self.tree.addTopLevelItem(item)

        # Add expected terminals that are not connected
        for store, terminals in self.expected_terminals.items():
            for terminal in terminals:
                if (store, terminal) not in [(k.split(',')[0], k.split(',')[1]) for k in connected_terminals.keys()]:
                    item = QTreeWidgetItem([store, terminal, 'N/A', 'N/A'])
                    item.setBackground(0, QColor(240, 128, 128))  # Light coral background
                    self.tree.addTopLevelItem(item)

    def update_status(self):
        self.update_tree()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TerminalStatusApp()
    window.show()
    sys.exit(app.exec_())
