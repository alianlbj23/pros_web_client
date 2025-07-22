import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from backend import Backend  # 引入後端邏輯

class IPInputWindow(QWidget):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.connected = False
        self.current_ip = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setFixedSize(300, 300)

        # IP 輸入
        ip_label = QLabel("Server IP:", self)
        self.ip_edit = QLineEdit(self)
        self.ip_edit.setPlaceholderText("e.g. 192.168.0.10")
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_edit)

        # Port 輸入
        port_label = QLabel("Port:", self)
        self.port_edit = QLineEdit(self)
        self.port_edit.setPlaceholderText("5000")
        port_layout = QHBoxLayout()
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_edit)

        # Connect / Disconnect
        self.btn_connect = QPushButton("Connect", self)
        self.btn_connect.clicked.connect(self.on_connect_click)

        # 其他功能按鈕
        self.btn_slam = QPushButton("Slam", self);        self.btn_slam.setVisible(False)
        self.btn_store_map = QPushButton("Store Map", self); self.btn_store_map.setVisible(False); self.btn_store_map.setEnabled(False)
        self.btn_loc  = QPushButton("Localization", self);   self.btn_loc.setVisible(False)
        self.btn_reset= QPushButton("Reset", self);          self.btn_reset.setVisible(False)

        # Layout
        layout = QVBoxLayout()
        layout.addLayout(ip_layout)
        layout.addLayout(port_layout)
        layout.addWidget(self.btn_connect)
        layout.addWidget(self.btn_slam)
        layout.addWidget(self.btn_store_map)
        layout.addWidget(self.btn_loc)
        layout.addWidget(self.btn_reset)
        self.setLayout(layout)

    def on_connect_click(self):
        ip = self.ip_edit.text().strip()
        port_text = self.port_edit.text().strip()

        # 檢查 IP
        if not Backend.validate_ip(ip):
            QMessageBox.warning(self, "Warning", "Invalid IP format.")
            return

        # 解析 port，沒填就用 5000
        if not port_text:
            port = 5000
        else:
            try:
                port = int(port_text)
            except ValueError:
                QMessageBox.warning(self, "Warning", "Invalid port format.")
                return

        # 呼叫後端處理連線／斷線
        self.backend.handle_connection(ip, port, self)

    def update_ui_on_connection(self, ip, port):
        self.connected = True
        self.current_ip = ip
        self.ip_edit.setText(ip)
        self.port_edit.setText(str(port))
        self.ip_edit.setEnabled(False)
        self.port_edit.setEnabled(False)
        self.btn_connect.setText("Disconnect")
        self.btn_slam.setVisible(True)
        self.btn_store_map.setVisible(True)
        self.btn_loc.setVisible(True)
        self.btn_reset.setVisible(True)

    def update_ui_on_disconnection(self):
        self.connected = False
        self.ip_edit.clear()
        self.port_edit.clear()
        self.ip_edit.setEnabled(True)
        self.port_edit.setEnabled(True)
        self.btn_connect.setText("Connect")
        self.btn_slam.setVisible(False)
        self.btn_store_map.setVisible(False)
        self.btn_loc.setVisible(False)
        self.btn_reset.setVisible(False)
        self.current_ip = ""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    backend = Backend()
    window = IPInputWindow(backend)
    window.show()
    sys.exit(app.exec_())
