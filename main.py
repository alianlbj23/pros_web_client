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
        self.loc_active = False
        self.current_ip = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setFixedSize(300, 300)  # 調大一點高度

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

        # Store Map button (hidden until connected)
        self.btn_store_map = QPushButton("Store Map", self)
        self.btn_store_map.clicked.connect(self.on_store_map_click)
        self.btn_store_map.setVisible(False)
        self.btn_store_map.setEnabled(False)

        # Localization button (hidden until connected)
        self.btn_loc = QPushButton("Localization", self)
        self.btn_loc.clicked.connect(self.on_loc_click)
        self.btn_loc.setVisible(False)

        # Reset button (hidden until connected)
        self.btn_reset = QPushButton("Reset", self)
        self.btn_reset.clicked.connect(self.on_reset_click)
        self.btn_reset.setVisible(False)

        # Current IP display
        self.current_ip_label = QLabel("", self)
        self.current_ip_label.setVisible(False)

        # Layout
        layout = QVBoxLayout()
        layout.addLayout(ip_layout)
        layout.addWidget(self.btn_connect)
        layout.addWidget(self.btn_slam)
        layout.addWidget(self.btn_store_map)   # 新增 Store Map 按鈕
        layout.addWidget(self.btn_loc)
        layout.addWidget(self.btn_reset)
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
                msg = data.get("message", "")
                if (
                    data.get("status") == "Script execution started"
                    or "already active" in msg
                ):
                    self._set_connected(ip)
                    info = (
                        "Connected and services started."
                        if data.get("status") == "Script execution started"
                        else "Already connected."
                    )
                    QMessageBox.information(self, "Info", info)
                else:
                    QMessageBox.warning(self, "Warning", f"Server error: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect: {e}")
        else:
            # Disconnect UI immediately, send stop in background
            ip = self.current_ip
            self._set_disconnected()
            threading.Thread(target=self._send_starcar_stop, args=(ip,)).start()

    def on_slam_click(self):
        if not self.slam_active:
            url = f"http://{self.current_ip}:5000/run-script/slam_ydlidar"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.slam_active = True
                    self.btn_slam.setText("Close Slam")
                    # disable localization button
                    self.btn_loc.setEnabled(False)
                    # enable store map button
                    self.btn_store_map.setEnabled(True)
                    QMessageBox.information(self, "Info", "Slam started.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start slam: {e}")
        else:
            self.slam_active = False
            self.btn_slam.setText("Slam")
            # re-enable localization button
            self.btn_loc.setEnabled(True)
            # disable store map button
            self.btn_store_map.setEnabled(False)
            threading.Thread(
                target=self._send_slam_stop, args=(self.current_ip,)
            ).start()

    def on_store_map_click(self):
        url = f"http://{self.current_ip}:5000/run-script/store_map"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            msg = data.get("message", "")
            if data.get("status") == "Script execution started":
                QMessageBox.information(self, "Info", "Store Map signal sent.")
            else:
                QMessageBox.warning(self, "Warning", f"Server error: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to store map: {e}")

    def on_loc_click(self):
        if not self.loc_active:
            url = f"http://{self.current_ip}:5000/run-script/localization_ydlidar"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.loc_active = True
                    self.btn_loc.setText("Close Localization")
                    # disable slam button
                    self.btn_slam.setEnabled(False)
                    # disable store map button
                    self.btn_store_map.setEnabled(False)
                    QMessageBox.information(self, "Info", "Localization started.")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to start localization: {e}"
                )
        else:
            self.loc_active = False
            self.btn_loc.setText("Localization")
            # re-enable slam button
            self.btn_slam.setEnabled(True)
            # 根據 slam_active 狀態判斷 store_map
            self.btn_store_map.setEnabled(self.slam_active)
            threading.Thread(
                target=self._send_loc_stop, args=(self.current_ip,)
            ).start()

    def on_reset_click(self):
        # Reset slam and localization states and UI
        self.slam_active = False
        self.btn_slam.setText("Slam")
        self.btn_slam.setEnabled(True)
        self.loc_active = False
        self.btn_loc.setText("Localization")
        self.btn_loc.setEnabled(True)
        self.btn_store_map.setEnabled(False)
        # Fire stop signals in background
        threading.Thread(target=self._send_reset, args=(self.current_ip,)).start()
        QMessageBox.information(self, "Info", "Reset signals sent.")

    def _send_slam_stop(self, ip: str):
        try:
            requests.get(f"http://{ip}:5000/run-script/slam_ydlidar_stop", timeout=5)
        except:
            pass

    def _send_loc_stop(self, ip: str):
        try:
            requests.get(
                f"http://{ip}:5000/run-script/localization_ydlidar_stop", timeout=5
            )
        except:
            pass

    def _send_starcar_stop(self, ip: str):
        try:
            requests.get(f"http://{ip}:5000/run-script/star_car_stop", timeout=5)
        except:
            pass

    def _send_reset(self, ip: str):
        # Fire both stop signals
        self._send_slam_stop(ip)
        self._send_loc_stop(ip)

    def _set_connected(self, ip: str):
        self.connected = True
        self.current_ip = ip
        self.ip_edit.setText(ip)
        self.ip_edit.setEnabled(False)
        self.btn_connect.setText("Disconnect")
        self.btn_slam.setVisible(True)
        self.btn_slam.setEnabled(True)
        self.btn_slam.setText("Slam")
        self.btn_store_map.setVisible(True)
        self.btn_store_map.setEnabled(False)
        self.btn_loc.setVisible(True)
        self.btn_loc.setEnabled(True)
        self.btn_loc.setText("Localization")
        self.btn_reset.setVisible(True)
        self.btn_reset.setText("Reset")
        self.slam_active = False
        self.loc_active = False
        self.current_ip_label.setText(f"Connected IP: {ip}")
        self.current_ip_label.setVisible(True)

    def _set_disconnected(self):
        self.connected = False
        self.slam_active = False
        self.loc_active = False
        self.ip_edit.clear()
        self.ip_edit.setEnabled(True)
        self.btn_connect.setText("Connect")
        self.btn_slam.setVisible(False)
        self.btn_slam.setText("Slam")
        self.btn_store_map.setVisible(False)
        self.btn_store_map.setEnabled(False)
        self.btn_loc.setVisible(False)
        self.btn_loc.setText("Localization")
        self.btn_reset.setVisible(False)
        self.btn_reset.setText("Reset")
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
            n = int(p)
            if n < 0 or n > 255:
                return False
        return True

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPInputWindow()
    window.show()
    sys.exit(app.exec_())
