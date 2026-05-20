from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QPushButton, 
                             QHeaderView, QDialog, QFormLayout, QLineEdit, 
                             QComboBox, QMessageBox, QRadioButton, QCheckBox,
                             QButtonGroup, QGroupBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ..models import Site



class SiteDialog(QDialog):
    def __init__(self, parent=None, site: Site = None):
        super().__init__(parent)
        self.site = site
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("添加站点" if not self.site else "编辑站点")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.url_input = QLineEdit()
        self.auth_method_combo = QComboBox()
        self.auth_method_combo.addItems(["Access Token + New-Api-User", "用户名 + 密码"])
        self.user_id_input = QLineEdit()
        self.token_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(["Root / 管理员权限", "普通用户权限"])
        
        if self.site:
            self.name_input.setText(self.site.name)
            self.url_input.setText(self.site.url)
            self.token_input.setText(self.site.token)
            self.user_id_input.setText(getattr(self.site, "user_id", ""))
            self.username_input.setText(getattr(self.site, "username", ""))
            self.password_input.setText(getattr(self.site, "password", ""))
            self.auth_method_combo.setCurrentIndex(1 if getattr(self.site, "auth_method", "access_token") == "password" else 0)
            self.auth_combo.setCurrentIndex(0 if self.site.auth_type == "admin" else 1)
        else:
            self.url_input.setPlaceholderText("https://api.newapi.com")
            self.user_id_input.setPlaceholderText("例如: 1")
            
        self.token_label = QLabel("Access Token:")
        self.user_id_label = QLabel("New-Api-User:")
        self.username_label = QLabel("用户名:")
        self.password_label = QLabel("密码:")

        form_layout.addRow("站点名称:", self.name_input)
        form_layout.addRow("接口地址 URL:", self.url_input)
        form_layout.addRow("登录方式:", self.auth_method_combo)
        form_layout.addRow(self.user_id_label, self.user_id_input)
        form_layout.addRow(self.token_label, self.token_input)
        form_layout.addRow(self.username_label, self.username_input)
        form_layout.addRow(self.password_label, self.password_input)
        form_layout.addRow("权限类型:", self.auth_combo)
        self.auth_method_combo.currentIndexChanged.connect(self.update_auth_fields)
        self.update_auth_fields()
        
        layout.addLayout(form_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        auth_type = "admin" if self.auth_combo.currentIndex() == 0 else "user"
        auth_method = "password" if self.auth_method_combo.currentIndex() == 1 else "access_token"
        return {
            "name": self.name_input.text().strip(),
            "url": self.url_input.text().strip(),
            "token": self.token_input.text().strip(),
            "user_id": self.user_id_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "auth_method": auth_method,
            "auth_type": auth_type
        }

    def update_auth_fields(self):
        use_password = self.auth_method_combo.currentIndex() == 1
        for widget in (self.token_label, self.token_input, self.user_id_label, self.user_id_input):
            widget.setVisible(not use_password)
        for widget in (self.username_label, self.username_input, self.password_label, self.password_input):
            widget.setVisible(use_password)


class SitePanel(QWidget):
    # Signals to communicate with Main Window
    source_changed = Signal(str)      # Emits site_id of the selected source site
    targets_changed = Signal(list)    # Emits list of site_ids of checked target sites
    site_edit_requested = Signal(str, dict) # Emits site_id, new_data
    site_add_requested = Signal(dict)       # Emits data
    site_delete_requested = Signal(str)    # Emits site_id
    test_connection_requested = Signal(str) # Emits site_id
    batch_test_requested = Signal(list)     # Emits list of site_ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sites = []
        self.source_radio_buttons = {}
        self.target_checkboxes = {}
        self.source_button_group = QButtonGroup(self)
        self.source_button_group.setExclusive(True)
        self.init_ui()

    def init_ui(self):
        # Set up outer layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        # Title
        title = QLabel("NewAPI 站点管理")
        title.setObjectName("panelTitle")
        self.layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["源", "目", "站点名称", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self.on_table_double_clicked)
        self.table.itemClicked.connect(self.on_table_row_clicked)
        self.table.itemSelectionChanged.connect(self.update_detail_panel)
        self.layout.addWidget(self.table)

        # Details Panel
        self.detail_group = QGroupBox("站点详细信息")
        detail_layout = QFormLayout(self.detail_group)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(6)
        
        self.detail_url_lbl = QLabel("未选择")
        self.detail_url_lbl.setWordWrap(True)
        self.detail_type_lbl = QLabel("未选择")
        self.detail_status_lbl = QLabel("未选择")
        self.detail_status_lbl.setWordWrap(True)
        
        detail_layout.addRow("接口地址:", self.detail_url_lbl)
        detail_layout.addRow("权限类型:", self.detail_type_lbl)
        detail_layout.addRow("连接状况:", self.detail_status_lbl)
        
        self.layout.addWidget(self.detail_group)

        # Control Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.clicked.connect(self.on_add_clicked)
        
        self.edit_btn = QPushButton("✏️ 编辑")
        self.edit_btn.clicked.connect(self.on_edit_clicked)
        
        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("删除操作已禁用。")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        
        self.test_btn = QPushButton("⚡ 测试连接")
        self.test_btn.clicked.connect(self.on_test_clicked)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.test_btn)
        self.layout.addLayout(btn_layout)

    def set_sites(self, sites: list):
        self.sites = sites
        
        # Clear existing button group mappings
        for btn in self.source_button_group.buttons():
            self.source_button_group.removeButton(btn)
        self.source_radio_buttons.clear()
        self.target_checkboxes.clear()

        self.table.setRowCount(len(sites))
        
        for idx, site in enumerate(sites):
            # Source Radio Button Cell
            source_rb = QRadioButton()
            source_rb.setStyleSheet("background-color: transparent; margin-left: 10px;")
            self.source_button_group.addButton(source_rb)
            self.source_radio_buttons[site.id] = source_rb
            
            # Target Checkbox Cell
            target_cb = QCheckBox()
            target_cb.setStyleSheet("background-color: transparent; margin-left: 10px;")
            self.target_checkboxes[site.id] = target_cb
            
            # Align widgets in centers of cell
            src_container = QWidget()
            src_layout = QHBoxLayout(src_container)
            src_layout.addWidget(source_rb)
            src_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            src_layout.setContentsMargins(0,0,0,0)
            
            tgt_container = QWidget()
            tgt_layout = QHBoxLayout(tgt_container)
            tgt_layout.addWidget(target_cb)
            tgt_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tgt_layout.setContentsMargins(0,0,0,0)

            self.table.setCellWidget(idx, 0, src_container)
            self.table.setCellWidget(idx, 1, tgt_container)

            # Name, Status items
            name_item = QTableWidgetItem(site.name)
            name_item.setData(Qt.ItemDataRole.UserRole, site.id) # Store ID
            
            status_text = "未测试"
            status_color = "#94a3b8"
            if site.status == "connected":
                status_text = "🟢 连接成功"
                status_color = "#10b981"
            elif site.status == "failed":
                status_text = "🔴 连接失败"
                status_color = "#f43f5e"
            elif site.status == "connecting":
                status_text = "⏳ 连接中..."
                status_color = "#38bdf8"
                
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Disable item direct edits
            for item in (name_item, status_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(idx, 2, name_item)
            self.table.setItem(idx, 3, status_item)

            # Wire up check state triggers
            source_rb.toggled.connect(lambda checked, s_id=site.id: self.on_source_toggled(s_id, checked))
            target_cb.stateChanged.connect(lambda state, s_id=site.id: self.on_target_state_changed(s_id, state))
            
        self.update_detail_panel()

    def get_selected_site_id(self) -> str:
        row = self.table.currentRow()
        if row >= 0:
            name_item = self.table.item(row, 2)
            if name_item:
                return name_item.data(Qt.ItemDataRole.UserRole)
        return ""

    def on_table_row_clicked(self, item: QTableWidgetItem):
        # We can auto load model details if clicked
        pass

    def on_table_double_clicked(self, item: QTableWidgetItem):
        self.on_edit_clicked()

    def on_source_toggled(self, site_id: str, checked: bool):
        if checked:
            # When selected as source, disable as target (a site can't sync to itself)
            if site_id in self.target_checkboxes:
                self.target_checkboxes[site_id].setChecked(False)
                self.target_checkboxes[site_id].setEnabled(False)
            
            # Re-enable other checkboxes
            for s_id, cb in self.target_checkboxes.items():
                if s_id != site_id:
                    cb.setEnabled(True)
                    
            self.source_changed.emit(site_id)

    def on_target_state_changed(self, site_id: str, state: int):
        checked_ids = []
        for s_id, cb in self.target_checkboxes.items():
            if cb.isChecked():
                checked_ids.append(s_id)
        self.targets_changed.emit(checked_ids)

    def on_add_clicked(self):
        dialog = SiteDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            error = self.validate_site_data(data)
            if error:
                QMessageBox.warning(self, "输入错误", error)
                return
            self.site_add_requested.emit(data)

    def on_edit_clicked(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.information(self, "提示", "请先选择要编辑的站点。")
            return
            
        site = next((s for s in self.sites if s.id == site_id), None)
        if not site:
            return
            
        dialog = SiteDialog(self, site)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            error = self.validate_site_data(data)
            if error:
                QMessageBox.warning(self, "输入错误", error)
                return
            self.site_edit_requested.emit(site_id, data)

    def validate_site_data(self, data: dict) -> str:
        if not data["name"] or not data["url"]:
            return "名称和 URL 不能为空。"
        if data.get("auth_method") == "password":
            if not data.get("username") or not data.get("password"):
                return "账号密码登录需要填写用户名和密码。"
        else:
            if not data.get("token") or not data.get("user_id"):
                return "Access Token 模式需要填写 Token 和 New-Api-User 用户 ID。"
        return ""

    def on_delete_clicked(self):
        QMessageBox.information(self, "删除已禁用", "当前版本禁止删除站点、模型或模型价格。")

    def on_test_clicked(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.information(self, "提示", "请选择要测试连接的站点。")
            return
        
        # Set status to Connecting visual state
        self.update_site_status(site_id, "connecting")
        self.test_connection_requested.emit(site_id)

    def update_site_status(self, site_id: str, status: str):
        for idx, site in enumerate(self.sites):
            if site.id == site_id:
                site.status = status
                status_text = "未测试"
                status_color = "#94a3b8"
                if status == "connected":
                    status_text = "🟢 连接成功"
                    status_color = "#10b981"
                elif status == "failed":
                    status_text = "🔴 连接失败"
                    status_color = "#f43f5e"
                elif status == "connecting":
                    status_text = "⏳ 连接中..."
                    status_color = "#38bdf8"
                
                status_item = self.table.item(idx, 3)
                if status_item:
                    status_item.setText(status_text)
                    status_item.setForeground(QColor(status_color))
                
                # If this is the currently selected row, update details as well
                if self.table.currentRow() == idx:
                    self.update_detail_panel()
                break
                
    def update_detail_panel(self):
        row = self.table.currentRow()
        if row >= 0 and row < len(self.sites):
            site = self.sites[row]
            self.detail_url_lbl.setText(site.url)
            
            auth_method_text = "账号密码登录" if getattr(site, "auth_method", "access_token") == "password" else "Access Token 登录"
            auth_str = ("管理员" if site.auth_type == "admin" else "普通用户") + f" ({auth_method_text})"
            self.detail_type_lbl.setText(auth_str)
            
            status_str = "未测试"
            if site.status == "connected":
                status_str = "🟢 连接成功"
            elif site.status == "failed":
                status_str = "🔴 连接失败"
            elif site.status == "connecting":
                status_str = "⏳ 连接中..."
            self.detail_status_lbl.setText(status_str)
        else:
            self.detail_url_lbl.setText("未选择")
            self.detail_type_lbl.setText("未选择")
            self.detail_status_lbl.setText("未选择")

    def get_source_site_id(self) -> str:
        for site_id, rb in self.source_radio_buttons.items():
            if rb.isChecked():
                return site_id
        return ""

    def get_target_site_ids(self) -> list:
        return [site_id for site_id, cb in self.target_checkboxes.items() if cb.isChecked()]
