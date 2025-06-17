import sys
import threading
import requests
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)


class IPInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.slam_active = False
        self.current_ip = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setFixedSize(300, 230)

        # IP input area
        ip_label = QLabel("Server IP:", self)
        self.ip_edit = QLineEdit(self)
        self.ip_edit.setPlaceholderText("e.g. 192.168.0.10")
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_edit)

        # Connect/Disconnect button
        self.btn_connect = QPushButton("Connect", self)
        self.btn_connect.clicked.connect(self.on_connect_click)

        # Slam button (hidden until connected)
        self.btn_slam = QPushButton("Slam", self)
        self.btn_slam.clicked.connect(self.on_slam_click)
        self.btn_slam.setVisible(False)

        # Current IP display
        self.current_ip_label = QLabel("", self)
        self.current_ip_label.setVisible(False)

        # Layout
        layout = QVBoxLayout()
        layout.addLayout(ip_layout)
        layout.addWidget(self.btn_connect)
        layout.addWidget(self.btn_slam)
        layout.addWidget(self.current_ip_label)
        self.setLayout(layout)

    def on_connect_click(self):
        ip = self.ip_edit.text().strip()
        if not self.validate_ip(ip):
            QMessageBox.warning(self, "Warning", "Invalid IP format.")
            return

        if not self.connected:
            url = f"http://{ip}:5000/run-script/star_car"
            try:
                resp = requests.get(url, timeout=5)
                data = resp.json()
                message = data.get("message", "")
                if (
                    data.get("status") == "Script execution started"
                    or "already active" in message
                ):
                    self._set_connected(ip)
                    QMessageBox.information(
                        self,
                        "Info",
                        (
                            "Connected and services started."
                            if data.get("status") == "Script execution started"
                            else "Already connected."
                        ),
                    )
                else:
                    QMessageBox.warning(self, "Warning", f"Server error: {message}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect: {e}")
        else:
            # Immediately update UI and send stop in background
            self._set_disconnected()
            threading.Thread(
                target=self._send_starcar_stop, args=(self.current_ip,)
            ).start()

    def on_slam_click(self):
        if not self.slam_active:
            url = f"http://{self.current_ip}:5000/run-script/slam_ydlidar"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.slam_active = True
                    self.btn_slam.setText("Close Slam")
                    QMessageBox.information(self, "Info", "Slam started.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start slam: {e}")
        else:
            # immediately send stop and reset UI
            self.slam_active = False
            self.btn_slam.setText("Slam")
            threading.Thread(
                target=self._send_slam_stop, args=(self.current_ip,)
            ).start()

    def _send_slam_stop(self, ip: str):
        try:
            requests.get(f"http://{ip}:5000/run-script/slam_ydlidar_stop", timeout=5)
        except:
            pass

    def _send_starcar_stop(self, ip: str):
        try:
            requests.get(f"http://{ip}:5000/run-script/star_car_stop", timeout=5)
        except:
            pass

    def _set_connected(self, ip: str):
        self.connected = True
        self.current_ip = ip
        self.ip_edit.setText(ip)
        self.ip_edit.setEnabled(False)
        self.btn_connect.setText("Disconnect")
        self.btn_slam.setVisible(True)
        self.slam_active = False
        self.current_ip_label.setText(f"Connected IP: {ip}")
        self.current_ip_label.setVisible(True)

    def _set_disconnected(self):
        self.connected = False
        self.slam_active = False
        self.ip_edit.clear()
        self.ip_edit.setEnabled(True)
        self.btn_connect.setText("Connect")
        self.btn_slam.setVisible(False)
        self.btn_slam.setText("Slam")
        self.current_ip_label.setVisible(False)
        self.current_ip = ""

    @staticmethod
    def validate_ip(ip: str) -> bool:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for p in parts:
            if not p.isdigit():
                return False
            num = int(p)
            if num < 0 or num > 255:
                return False
        return True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPInputWindow()
    window.show()
    sys.exit(app.exec_())
