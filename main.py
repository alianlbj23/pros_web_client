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
    QSlider,
    QFormLayout,
)
from PyQt5.QtCore import Qt  # 引入 Qt 模塊
import yaml
from PyQt5.QtWidgets import QScrollArea
import roslibpy  # ← 新增
import math
import time


class IPInputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.slam_active = False
        self.loc_active = False
        self.current_ip = ""
        self.current_port = 5000  # 預設 port
        self.selected_lidar = "ydlidar"  # 預設選擇 "lidar"
        self.wheel_pub = None  # roslibpy.Topic for wheel
        self.camera_active = False  # 新增 camera 狀態
        self.yolo_active = False  # 新增 YOLO 狀態

        # ✅ 初始化 YAML 中的 key_map 和 joint_limits
        with open("keyboard.yaml", "r") as f:
            config = yaml.safe_load(f)
            self.key_map = config.get("key_mappings", {})
            self.joint_limits = config.get("arm_joint_limits", {})

        self.joint_sliders = {}  # key: joint_name, value: slider

        # ✅ 最後再初始化 UI（要用到 joint_limits）
        self.init_ui()

        self.ros = None  # roslibpy.Ros 物件
        self.rosbridge_port = 9090  # 可改成你需要的 port
        self.arm_pub = None  # roslibpy.Topic for arm joints

    def _connect_rosbridge(
        self, ip: str, port: int = 9090, timeout: int = 5, max_retries: int = 5
    ):
        for attempt in range(1, max_retries + 1):
            ros = roslibpy.Ros(host=ip, port=port)
            try:
                print(
                    f"[INFO] Attempting to connect to ROSBridge (try {attempt}/{max_retries})..."
                )
                ros.run(timeout=timeout)
                if ros.is_connected:
                    self.ros = ros

                    # wheel publisher
                    self.wheel_pub = roslibpy.Topic(
                        self.ros, "/car_C_rear_wheel", "std_msgs/Float32MultiArray"
                    )
                    self.wheel_pub.advertise()

                    # ★ arm publisher
                    self.arm_pub = roslibpy.Topic(
                        self.ros, "/robot_arm", "trajectory_msgs/JointTrajectoryPoint"
                    )
                    self.arm_pub.advertise()

                    print(f"[INFO] Connected to ROSBridge on attempt {attempt}")
                    return True, ""
                else:
                    print("[WARN] roslibpy connected=False")

            except Exception as e:
                print(f"[ERROR] ROSBridge connection failed on attempt {attempt}: {e}")

            time.sleep(1)  # 每次間隔 1 秒再嘗試

        return False, f"Failed to connect after {max_retries} attempts"

    def _disconnect_rosbridge(self):
        if self.wheel_pub:
            try:
                self.wheel_pub.unadvertise()
            except:
                pass
            self.wheel_pub = None

        if self.arm_pub:
            try:
                self.arm_pub.unadvertise()
            except:
                pass
            self.arm_pub = None

        if self.ros and self.ros.is_connected:
            try:
                self.ros.terminate()
            except:
                pass
        self.ros = None

    def publish_robot_arm(self, joint_values):
        """
        joint_values: list[float] 依序為各關節角度
        trajectory_msgs/JointTrajectoryPoint:
        float64[] positions
        float64[] velocities
        float64[] accelerations
        float64[] effort
        duration  time_from_start
        """
        if not (self.ros and self.ros.is_connected and self.arm_pub):
            print("[WARN] ROS not connected, skip robot_arm publish.")
            return

        msg = roslibpy.Message(
            {
                "positions": list(map(float, joint_values)),
                "velocities": [],
                "accelerations": [],
                "effort": [],
                "time_from_start": {"secs": 0, "nsecs": 0},
            }
        )
        self.arm_pub.publish(msg)

    def publish_wheel_speed(self, speeds):
        """speeds: list[float or int]"""
        if not (self.ros and self.ros.is_connected and self.wheel_pub):
            print("[WARN] ROS not connected, skip publish.")
            return
        msg = roslibpy.Message(
            {"layout": {"dim": [], "data_offset": 0}, "data": list(map(float, speeds))}
        )
        self.wheel_pub.publish(msg)

    def send_joint_command(self):
        if not self.connected:
            return

        joint_values = []
        for joint in sorted(self.joint_sliders.keys()):  # 保持順序一致
            joint_values.append(self.joint_sliders[joint].value())
        joint_values_deg = [
            self.joint_sliders[j].value() for j in sorted(self.joint_sliders.keys())
        ]
        joint_values_rad = [math.radians(v) for v in joint_values_deg]
        self.publish_robot_arm(joint_values_rad)

    def on_joint_slider_changed(self, joint_name):
        value = self.joint_sliders[joint_name].value()
        self.joint_labels[joint_name].setText(str(value))
        self.send_joint_command()

    def reset_all_joint_sliders(self):
        for joint_name, slider in self.joint_sliders.items():
            default_val = self.joint_limits[joint_name].get("default", 0)
            slider.setValue(default_val)
            self.joint_labels[joint_name].setText(str(default_val))

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setFixedSize(600, 600)

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
        self.lidar_combo.setVisible(False)  # 隱藏 LIDAR 下拉選單
        lidar_label.setVisible(False)  # 隱藏 Label

        self.lidar_label = lidar_label  # 保留指標方便後面控制可見性

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

        # Camera button
        self.btn_camera = QPushButton("Open Camera", self)
        self.btn_camera.clicked.connect(self.on_camera_click)
        self.btn_camera.setVisible(False)  # 初始為隱藏
        layout.addWidget(self.btn_camera)

        # YOLO button (新增)
        self.btn_yolo = QPushButton("Open YOLO", self)
        self.btn_yolo.clicked.connect(self.on_yolo_click)
        self.btn_yolo.setVisible(False)  # 初始為隱藏
        self.btn_yolo.setEnabled(False)  # 初始為禁用
        layout.addWidget(self.btn_yolo)

        layout.addWidget(self.btn_reset)
        layout.addWidget(self.current_ip_label)
        layout.addWidget(self.key_label)

        self.btn_reset_joints = QPushButton("Reset Joints", self)
        self.btn_reset_joints.clicked.connect(self.reset_all_joint_sliders)
        self.btn_reset_joints.setVisible(False)  # 初始為隱藏
        layout.addWidget(self.btn_reset_joints)

        self.form_layout_widget = QWidget()
        form_layout = QFormLayout()
        self.form_layout_widget.setLayout(form_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.form_layout_widget)

        self.joint_labels = {}  # key: joint_name, value: QLabel

        for joint_name, limits in self.joint_limits.items():
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(limits["min"])
            slider.setMaximum(limits["max"])
            slider.setValue(limits.get("default", (limits["min"] + limits["max"]) // 2))

            label = QLabel(str(slider.value()))
            self.joint_labels[joint_name] = label

            # 包成一個水平區塊（slider + label）
            h_layout = QHBoxLayout()
            h_layout.addWidget(slider)
            h_layout.addWidget(label)

            slider.valueChanged.connect(
                lambda _, name=joint_name: self.on_joint_slider_changed(name)
            )

            slider.valueChanged.connect(
                lambda _, name=joint_name: self.on_joint_slider_changed(name)
            )
            self.joint_sliders[joint_name] = slider
            form_layout.addRow(
                f"{joint_name} ({limits['min']}~{limits['max']})", h_layout
            )

        layout.addLayout(form_layout)
        self.setLayout(layout)
        self.form_layout_widget.setVisible(False)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.btn_reset_joints)

    def keyPressEvent(self, event):
        if self.connected:
            key = event.text()
            if key:
                self.key_label.setText(f"Key Pressed: {key}")
                if key in self.key_map:
                    wheel_speed = self.key_map[key]  # list
                    # ★ 用 roslibpy 發
                    self.publish_wheel_speed(wheel_speed)
                else:
                    self.key_label.setText(f"Key '{key}' not mapped.")

    def on_camera_click(self):
        ip = self.current_ip
        port = self.current_port

        if not ip:
            QMessageBox.warning(self, "Warning", "IP not connected.")
            return

        if not self.camera_active:
            # 開啟 Camera
            url = f"http://{ip}:{port}/run-script/camera"
            try:
                resp = requests.get(url, timeout=5)
                data = resp.json()
                msg = data.get("message", "")

                if (
                    data.get("status") == "Script execution started"
                    or "already active" in msg
                    or "already running" in msg
                ):
                    self.camera_active = True
                    self.btn_camera.setText("Close Camera")
                    self.btn_yolo.setVisible(True)  # 顯示 YOLO 按鈕
                    self.btn_yolo.setEnabled(True)  # 啟用 YOLO 按鈕

                    info = (
                        "Camera started."
                        if data.get("status") == "Script execution started"
                        else "Camera already running."
                    )
                    QMessageBox.information(self, "Info", info)
                else:
                    QMessageBox.warning(
                        self, "Warning", f"Failed to start camera: {msg}"
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start camera: {e}")
        else:
            # 關閉 Camera
            self.camera_active = False
            self.btn_camera.setText("Open Camera")
            self.btn_yolo.setVisible(False)  # 隱藏 YOLO 按鈕

            # 如果 YOLO 正在運行，也要關閉它
            if self.yolo_active:
                self.yolo_active = False
                self.btn_yolo.setText("Open YOLO")
                threading.Thread(target=self._send_yolo_stop, args=(ip, port)).start()

            threading.Thread(target=self._send_camera_stop, args=(ip, port)).start()

    def on_yolo_click(self):
        ip = self.current_ip
        port = self.current_port

        if not ip:
            QMessageBox.warning(self, "Warning", "IP not connected.")
            return

        if not self.camera_active:
            QMessageBox.warning(self, "Warning", "Camera must be started first.")
            return

        if not self.yolo_active:
            # 開啟 YOLO
            url = f"http://{ip}:{port}/run-script/yolo"
            try:
                resp = requests.get(url, timeout=5)
                data = resp.json()
                msg = data.get("message", "")

                if (
                    data.get("status") == "Script execution started"
                    or "already active" in msg
                    or "already running" in msg
                ):
                    self.yolo_active = True
                    self.btn_yolo.setText("Close YOLO")

                    info = (
                        "YOLO started."
                        if data.get("status") == "Script execution started"
                        else "YOLO already running."
                    )
                    QMessageBox.information(self, "Info", info)
                else:
                    QMessageBox.warning(self, "Warning", f"Failed to start YOLO: {msg}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start YOLO: {e}")
        else:
            # 關閉 YOLO
            self.yolo_active = False
            self.btn_yolo.setText("Open YOLO")
            threading.Thread(target=self._send_yolo_stop, args=(ip, port)).start()

    def _send_yolo_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/yolo_stop", timeout=5)
        except:
            pass

    def _send_camera_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/camera_stop", timeout=5)
        except:
            pass

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

        # Port 預設 5000
        if not port_text:
            port = 5000
        else:
            try:
                port = int(port_text)
            except ValueError:
                QMessageBox.warning(self, "Warning", "Invalid port format.")
                return

        # －－－－－－－－ Connect 邏輯 －－－－－－－－#
        if not self.connected:
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
                    # 設定已連線狀態
                    self._set_connected(ip, port)

                    # 嘗試連 rosbridge
                    ok, err = self._connect_rosbridge(
                        ip, self.rosbridge_port, timeout=5
                    )
                    if ok:
                        QMessageBox.information(
                            self,
                            "ROSBridge",
                            f"Connected to ws://{ip}:{self.rosbridge_port}",
                        )
                    else:
                        QMessageBox.warning(
                            self,
                            "ROSBridge",
                            f"ROSBridge connect failed: {err}",
                        )

                    info = (
                        "Connected and services started."
                        if data.get("status") == "Script execution started"
                        else "Already connected."
                    )
                    QMessageBox.information(self, "Info", info)

                    # 顯示 LIDAR 選擇
                    self.lidar_combo.setVisible(True)
                    self.lidar_label.setVisible(True)

                else:
                    QMessageBox.warning(self, "Warning", f"Server error: {msg}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect: {e}")

        # －－－－－－－－ Disconnect 邏輯 －－－－－－－－#
        else:
            ip0, port0 = self.current_ip, self.current_port
            # 先更新 UI 狀態
            self._set_disconnected()
            # 發出 stop
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
        self.lidar_combo.setVisible(True)
        self.lidar_label.setVisible(True)
        self.form_layout_widget.setVisible(True)
        self.btn_reset_joints.setVisible(True)
        self.btn_camera.setVisible(True)
        self.btn_camera.setText("Open Camera")
        self.camera_active = False
        # YOLO 按鈕初始為隱藏，只有 camera 開啟時才顯示
        self.btn_yolo.setVisible(False)
        self.btn_yolo.setText("Open YOLO")
        self.btn_yolo.setEnabled(False)
        self.yolo_active = False

    def _set_disconnected(self):
        self.connected = False
        self.slam_active = False
        self.loc_active = False

        # 保存當前的IP和port以用於停止服務
        current_ip = self.current_ip
        current_port = self.current_port

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
        self.btn_reset_joints.setVisible(False)
        self._disconnect_rosbridge()

        # 如果 YOLO 正在運行，先停止它
        if self.yolo_active and current_ip:
            self.yolo_active = False
            threading.Thread(
                target=self._send_yolo_stop, args=(current_ip, current_port)
            ).start()

        # 如果 Camera 正在運行，也要停止它
        if self.camera_active and current_ip:
            self.camera_active = False
            threading.Thread(
                target=self._send_camera_stop, args=(current_ip, current_port)
            ).start()

        self.btn_camera.setVisible(False)
        self.camera_active = False
        self.btn_yolo.setVisible(False)  # 隱藏 YOLO 按鈕
        self.yolo_active = False

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
