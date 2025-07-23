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
    QComboBox,
)
from PyQt5.QtCore import Qt  # 引入 Qt 模塊
import yaml


class IPInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.slam_active = False
        self.loc_active = False
        self.current_ip = ""
        self.current_port = 5000  # 預設 port
        self.selected_lidar = "ydlidar"  # 預設選擇 "lidar"
        self.init_ui()
        with open("keyboard.yaml", "r") as f:
            self.key_map = yaml.safe_load(f).get("key_mappings", {})

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setFixedSize(300, 400)

        # IP input area
        ip_label = QLabel("Server IP:", self)
        self.ip_edit = QLineEdit(self)
        self.ip_edit.setPlaceholderText("e.g. 192.168.0.10")
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_edit)

        # Port input area
        port_label = QLabel("Port:", self)
        self.port_edit = QLineEdit(self)
        self.port_edit.setPlaceholderText("5000")
        port_layout = QHBoxLayout()
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_edit)

        # Connect/Disconnect button
        self.btn_connect = QPushButton("Connect", self)
        self.btn_connect.clicked.connect(self.on_connect_click)

        # LIDAR selection (ComboBox)
        lidar_label = QLabel("Select LIDAR:", self)
        self.lidar_combo = QComboBox(self)
        self.lidar_combo.addItems(["ydlidar", "oradarlidar"])
        self.lidar_combo.currentIndexChanged.connect(self.update_lidar_selection)

        # Slam button
        self.btn_slam = QPushButton("Slam", self)
        self.btn_slam.clicked.connect(self.on_slam_click)
        self.btn_slam.setVisible(False)

        # Store Map button
        self.btn_store_map = QPushButton("Store Map", self)
        self.btn_store_map.clicked.connect(self.on_store_map_click)
        self.btn_store_map.setVisible(False)
        self.btn_store_map.setEnabled(False)

        # Localization button
        self.btn_loc = QPushButton("Localization", self)
        self.btn_loc.clicked.connect(self.on_loc_click)
        self.btn_loc.setVisible(False)

        # Reset button
        self.btn_reset = QPushButton("Reset", self)
        self.btn_reset.clicked.connect(self.on_reset_click)
        self.btn_reset.setVisible(False)

        # Current IP label
        self.current_ip_label = QLabel("", self)
        self.current_ip_label.setVisible(False)

        # Key display
        self.key_label = QLabel("Press a key", self)
        self.key_label.setAlignment(Qt.AlignCenter)
        self.key_label.setStyleSheet("font-size: 18px;")

        # Layout
        layout = QVBoxLayout()
        layout.addLayout(ip_layout)
        layout.addLayout(port_layout)
        layout.addWidget(self.btn_connect)
        layout.addWidget(lidar_label)
        layout.addWidget(self.lidar_combo)  # Add the lidar combo box here
        layout.addWidget(self.btn_slam)
        layout.addWidget(self.btn_store_map)
        layout.addWidget(self.btn_loc)
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.current_ip_label)
        layout.addWidget(self.key_label)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        if self.connected:
            key = event.text()
            if key:
                self.key_label.setText(f"Key Pressed: {key}")
                # 查找對應的輪速指令
                if key in self.key_map:
                    wheel_speed = self.key_map[key]
                    wheel_str = "_".join(map(str, wheel_speed))
                    url = f"http://{self.current_ip}:{self.current_port}/wheel/{wheel_str}"
                    threading.Thread(
                        target=self.send_wheel_command, args=(url,)
                    ).start()
                else:
                    self.key_label.setText(f"Key '{key}' not mapped.")

    def send_wheel_command(self, url):
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code != 200:
                print(f"[WARN] Server response: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[ERROR] Failed to send wheel command: {e}")

    def update_lidar_selection(self):
        """
        Update the selected LIDAR type based on the combo box selection.
        """
        self.selected_lidar = self.lidar_combo.currentText()

    def on_connect_click(self):
        ip = self.ip_edit.text().strip()
        port_text = self.port_edit.text().strip()

        if not self.validate_ip(ip):
            QMessageBox.warning(self, "Warning", "Invalid IP format.")
            return

        # 只有沒輸入才給預設
        if not port_text:
            port = 5000
        else:
            try:
                port = int(port_text)
            except ValueError:
                QMessageBox.warning(self, "Warning", "Invalid port format.")
                return

        if not self.connected:
            # 根據 selected_lidar 動態修改 URL
            url = f"http://{ip}:{port}/run-script/star_car"
            try:
                resp = requests.get(url, timeout=5)
                data = resp.json()
                msg = data.get("message", "")
                if (
                    data.get("status") == "Script execution started"
                    or "already active" in msg
                    or "Containers for 'star_car' already running" in msg
                ):
                    # 如果 LIDAR 已經在跑，顯示訊息並進入選單
                    if (
                        "already active" in msg
                        or "Containers for 'star_car' already running" in msg
                    ):
                        QMessageBox.information(
                            self, "Info", "Service is already running."
                        )
                    # 連線成功，記下 IP & port
                    self._set_connected(ip, port)
                    info = (
                        "Connected and services started."
                        if data.get("status") == "Script execution started"
                        else "Already connected."
                    )
                    QMessageBox.information(self, "Info", info)
                    # 顯示 LIDAR 選擇框
                    self.lidar_combo.setVisible(True)
                else:
                    QMessageBox.warning(self, "Warning", f"Server error: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect: {e}")
        else:
            # Disconnect
            ip0, port0 = self.current_ip, self.current_port
            self._set_disconnected()
            threading.Thread(target=self._send_starcar_stop, args=(ip0, port0)).start()

    def on_slam_click(self):
        if not self.slam_active:
            # 根據 selected_lidar 動態修改 URL
            url = f"http://{self.current_ip}:{self.current_port}/run-script/slam_{self.selected_lidar}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.slam_active = True
                    self.btn_slam.setText("Close Slam")
                    self.btn_loc.setEnabled(False)
                    self.btn_store_map.setEnabled(True)
                    QMessageBox.information(self, "Info", "Slam started.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start slam: {e}")
        else:
            self.slam_active = False
            self.btn_slam.setText("Slam")
            self.btn_loc.setEnabled(True)
            self.btn_store_map.setEnabled(False)
            threading.Thread(
                target=self._send_slam_stop, args=(self.current_ip, self.current_port)
            ).start()

    def on_store_map_click(self):
        url = f"http://{self.current_ip}:{self.current_port}/run-script/store_map"
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
            # 根據 selected_lidar 動態修改 URL
            url = f"http://{self.current_ip}:{self.current_port}/run-script/localization_{self.selected_lidar}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.loc_active = True
                    self.btn_loc.setText("Close Localization")
                    self.btn_slam.setEnabled(False)
                    self.btn_store_map.setEnabled(False)
                    QMessageBox.information(self, "Info", "Localization started.")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to start localization: {e}"
                )
        else:
            self.loc_active = False
            self.btn_loc.setText("Localization")
            self.btn_slam.setEnabled(True)
            self.btn_store_map.setEnabled(self.slam_active)
            threading.Thread(
                target=self._send_loc_stop, args=(self.current_ip, self.current_port)
            ).start()

    def on_reset_click(self):
        self.slam_active = False
        self.btn_slam.setText("Slam")
        self.btn_slam.setEnabled(True)
        self.loc_active = False
        self.btn_loc.setText("Localization")
        self.btn_loc.setEnabled(True)
        self.btn_store_map.setEnabled(False)
        # stop slam & loc
        ip0, port0 = self.current_ip, self.current_port
        threading.Thread(target=self._send_slam_stop, args=(ip0, port0)).start()
        threading.Thread(target=self._send_loc_stop, args=(ip0, port0)).start()
        # 重新發送 star_car 請求以重啟服務
        # 直接發送 star_car 請求，而不觸發其他狀態改變
        url = f"http://{ip0}:{port0}/run-script/star_car"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            msg = data.get("message", "")
            if (
                data.get("status") == "Script execution started"
                or "already active" in msg
            ):
                QMessageBox.information(self, "Info", "Service restarted successfully.")
            else:
                QMessageBox.warning(self, "Warning", f"Server error: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to restart service: {e}")

        # 保持畫面原來的狀態
        QMessageBox.information(self, "Info", "Reset signals sent.")

    # -- stop functions 都帶入 port --
    def _send_slam_stop(self, ip: str, port: int):
        try:
            requests.get(
                f"http://{ip}:{port}/run-script/slam_{self.selected_lidar}_stop",
                timeout=5,
            )
        except:
            pass

    def _send_loc_stop(self, ip: str, port: int):
        try:
            requests.get(
                f"http://{ip}:{port}/run-script/localization_{self.selected_lidar}_stop",
                timeout=5,
            )
        except:
            pass

    def _send_starcar_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/star_car_stop", timeout=5)
        except:
            pass

    # UI 更新並記錄 port
    def _set_connected(self, ip: str, port: int):
        self.connected = True
        self.current_ip = ip
        self.current_port = port
        self.ip_edit.setText(ip)
        self.port_edit.setText(str(port))
        self.ip_edit.setEnabled(False)
        self.port_edit.setEnabled(False)
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
        self.current_ip_label.setText(f"Connected IP: {ip}")
        self.current_ip_label.setVisible(True)

    def _set_disconnected(self):
        self.connected = False
        self.slam_active = False
        self.loc_active = False
        self.ip_edit.clear()
        self.port_edit.clear()
        self.ip_edit.setEnabled(True)
        self.port_edit.setEnabled(True)
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
