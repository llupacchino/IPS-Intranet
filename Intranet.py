import sys
import logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QTextEdit, QPushButton, QDialog
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
import socketio
import requests
import json
import subprocess
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class CLIWindow(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("CLI")
        self.setGeometry(150, 150, 800, 600)
        self.setStyleSheet("background-color: black;")

        self.layout = QVBoxLayout(self)

        self.cli_output = QTextEdit(self)
        self.cli_output.setReadOnly(True)
        self.cli_output.setStyleSheet("background-color: black; color: white; font: 10pt 'Courier New';")
        self.cli_input = QTextEdit(self)
        self.cli_input.setFixedHeight(50)
        self.cli_input.setStyleSheet("background-color: black; color: white; font: 10pt 'Courier New';")
        self.cli_input.setPlaceholderText("Enter command here...")

        self.execute_button = QPushButton("Execute", self)
        self.execute_button.setStyleSheet("background-color: gray; color: white;")
        self.execute_button.clicked.connect(self.execute_command)

        self.layout.addWidget(self.cli_output)
        self.layout.addWidget(self.cli_input)
        self.layout.addWidget(self.execute_button)

    def execute_command(self):
        command = self.cli_input.toPlainText().strip()
        if command:
            if command == "terminal flush":
                self.parent().flush_unknown_connections()
                output = "Flushed all unknown connections."
            else:
                try:
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
                except subprocess.CalledProcessError as e:
                    output = e.output
            self.cli_output.append(f"> {command}\n{output}")
            self.cli_input.clear()

class TerminalStatusApp(QMainWindow):
    update_signal = pyqtSignal(dict)

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

        # CLI Button
        self.cli_button = QPushButton("CLI", self)
        self.cli_button.clicked.connect(self.open_cli_window)
        self.layout.addWidget(self.cli_button)

        # Set up SocketIO client
        self.sio = socketio.Client()
        self.sio.on('update_status', self.on_update_status)
        self.sio.connect("http://54.85.104.167:5000")  # Updated to public server IP

        self.load_expected_terminals()
        self.update_status()

        # Set up a timer to update the status every 15 seconds (reduce polling frequency)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(15000)

        # Initialize a list to store unknown connections
        self.unknown_connections = []
        self.previous_states = {}

        # Connect the update signal to the update_tree method
        self.update_signal.connect(self.update_tree)

    def load_expected_terminals(self):
        with open('expected_terminals.json') as f:
            self.expected_terminals = json.load(f)

    def on_update_status(self, data):
        logging.debug("Received update status")
        self.update_signal.emit(data)

    def update_tree(self, connected_terminals):
        logging.debug("Updating tree")
        self.connected_terminals = connected_terminals
        self.tree.clear()
        self.unknown_connections = []  # Reset unknown connections list

        # Add connected terminals
        for key, info in self.connected_terminals.items():
            if ',' in key:
                store, terminal = key.split(',')
                ip = info.get('ip', 'N/A')
                isp = info.get('isp', 'N/A')
                status = info.get('status', 'disconnected')

                item = QTreeWidgetItem([store, terminal, ip, isp])
                if status == 'connected':
                    item.setBackground(0, QColor(144, 238, 144))  # Light green background
                else:
                    item.setBackground(0, QColor(240, 128, 128))  # Light coral background
                self.tree.addTopLevelItem(item)

                # Track unknown connections
                if (store, terminal) not in [(k.split(',')[0], k.split(',')[1]) for k in self.expected_terminals.keys() if ',' in k]:
                    self.unknown_connections.append((store, terminal))
            else:
                logging.warning(f"Skipping invalid key: {key}")

        # Add expected terminals that are not connected
        for store, terminals in self.expected_terminals.items():
            for terminal in terminals:
                if (store, terminal) not in [(k.split(',')[0], k.split(',')[1]) for k in self.connected_terminals.keys() if ',' in k]:
                    item = QTreeWidgetItem([store, terminal, 'N/A', 'N/A'])
                    item.setBackground(0, QColor(240, 128, 128))  # Light coral background
                    self.tree.addTopLevelItem(item)

    def update_status(self):
        try:
            response = requests.get("http://54.85.104.167:5000/status")  # Updated to public server IP
            if response.status_code == 200:
                self.connected_terminals = response.json()
                self.update_signal.emit(self.connected_terminals)
            else:
                logging.error(f"Error fetching status: {response.status_code}")
                self.connected_terminals = {}
        except Exception as e:
            logging.error(f"Error fetching status: {e}")
            self.connected_terminals = {}

    def flush_unknown_connections(self):
        expected_keys = [(store, terminal) for store, terminals in self.expected_terminals.items() for terminal in terminals]
        for i in range(self.tree.topLevelItemCount() - 1, -1, -1):
            item = self.tree.topLevelItem(i)
            store = item.text(0)
            terminal = item.text(1)
            if (store, terminal) not in expected_keys and item.text(2) != 'N/A':
                self.tree.takeTopLevelItem(i)
                if (store, terminal) in self.previous_states:
                    del self.previous_states[(store, terminal)]
        self.unknown_connections = []  # Clear unknown connections list
        logging.debug("Flushed unknown connections")

    def open_cli_window(self):
        self.cli_window = CLIWindow(self)
        self.cli_window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TerminalStatusApp()
    window.show()
    sys.exit(app.exec_())
