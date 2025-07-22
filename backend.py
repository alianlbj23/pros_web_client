import requests
from threading import Thread
from PyQt5.QtWidgets import QMessageBox

class Backend:
    def __init__(self):
        self.connected = False
        self.current_ip = ""
        self.current_port = 5000
        self.slam_active = False
        self.loc_active = False

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

    def handle_connection(self, ip: str, port: int, frontend):
        if not self.connected:
            self.connect_to_server(ip, port, frontend)
        else:
            self.disconnect_from_server(frontend)

    def connect_to_server(self, ip: str, port: int, frontend):
        url = f"http://{ip}:{port}/run-script/star_car"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            msg = data.get("message", "")
            if data.get("status") == "Script execution started" or "already active" in msg:
                self.set_connected(ip, port)
                frontend.update_ui_on_connection(ip, port)
                QMessageBox.information(None, "Info", "Connected and services started.")
            else:
                QMessageBox.warning(None, "Warning", f"Server error: {msg}")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to connect: {e}")

    def disconnect_from_server(self, frontend):
        frontend.update_ui_on_disconnection()
        Thread(target=self._send_starcar_stop, args=(self.current_ip, self.current_port)).start()
        self.set_disconnected()

    def set_connected(self, ip: str, port: int):
        self.connected = True
        self.current_ip = ip
        self.current_port = port
        self.slam_active = False
        self.loc_active = False

    def set_disconnected(self):
        self.connected = False
        self.current_ip = ""
        self.current_port = 5000
        self.slam_active = False
        self.loc_active = False

    def start_slam(self):
        if not self.slam_active:
            url = f"http://{self.current_ip}:{self.current_port}/run-script/slam_ydlidar"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.slam_active = True
                    QMessageBox.information(None, "Info", "Slam started.")
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to start slam: {e}")
        else:
            self.slam_active = False
            Thread(target=self._send_slam_stop, args=(self.current_ip, self.current_port)).start()

    def store_map(self):
        url = f"http://{self.current_ip}:{self.current_port}/run-script/store_map"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            msg = data.get("message", "")
            if data.get("status") == "Script execution started":
                QMessageBox.information(None, "Info", "Store Map signal sent.")
            else:
                QMessageBox.warning(None, "Warning", f"Server error: {msg}")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to store map: {e}")

    def localization(self):
        if not self.loc_active:
            url = f"http://{self.current_ip}:{self.current_port}/run-script/localization_ydlidar"
            try:
                resp = requests.get(url, timeout=5)
                if resp.json().get("status") == "Script execution started":
                    self.loc_active = True
                    QMessageBox.information(None, "Info", "Localization started.")
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to start localization: {e}")
        else:
            self.loc_active = False
            Thread(target=self._send_loc_stop, args=(self.current_ip, self.current_port)).start()

    # 停止相關服務的私有方法，都改用 current_port
    def _send_slam_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/slam_ydlidar_stop", timeout=5)
        except:
            pass

    def _send_loc_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/localization_ydlidar_stop", timeout=5)
        except:
            pass

    def _send_starcar_stop(self, ip: str, port: int):
        try:
            requests.get(f"http://{ip}:{port}/run-script/star_car_stop", timeout=5)
        except:
            pass
