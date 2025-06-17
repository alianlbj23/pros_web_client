import sys
import requests
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox

class IPInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('IP Address Input')
        self.setFixedSize(300, 150)

        # Label
        label = QLabel('Enter Server IP:', self)

        # Text field
        self.ip_edit = QLineEdit(self)
        self.ip_edit.setPlaceholderText('e.g. 192.168.0.10')

        # Button
        self.btn = QPushButton('Connect', self)
        self.btn.clicked.connect(self.on_connect_click)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.ip_edit)
        layout.addWidget(self.btn)
        self.setLayout(layout)

    def on_connect_click(self):
        ip = self.ip_edit.text().strip()
        if not self.validate_ip(ip):
            QMessageBox.warning(self, 'Warning', 'Invalid IP format.')
            return

        if not self.connected:
            # Attempt to send start signal
            try:
                url = f'http://{ip}:5000/run-script/star_car'
                resp = requests.get(url, timeout=5)
                data = resp.json()
                if data.get('status') == 'Script execution started':
                    self.connected = True
                    self.btn.setText('Disconnect')
                    QMessageBox.information(self, 'Info', 'Started services.')
                else:
                    QMessageBox.warning(self, 'Warning', f"Server error: {data.get('message')}")
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to connect: {e}')
        else:
            # Send stop signal
            try:
                url = f'http://{ip}:5000/run-script/star_car_stop'
                resp = requests.get(url, timeout=5)
                data = resp.json()
                if data.get('status') == 'success':
                    self.connected = False
                    self.btn.setText('Connect')
                    QMessageBox.information(self, 'Info', 'Stopped services.')
                else:
                    QMessageBox.warning(self, 'Warning', f"Server error: {data.get('message')}")
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to disconnect: {e}')

    @staticmethod
    def validate_ip(ip: str) -> bool:
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit():
                return False
            num = int(p)
            if num < 0 or num > 255:
                return False
        return True

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = IPInputWindow()
    window.show()
    sys.exit(app.exec_())
