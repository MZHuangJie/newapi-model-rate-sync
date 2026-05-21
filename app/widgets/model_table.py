from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QCheckBox, QTabBar)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ..models import ModelPricing


class ModelTable(QWidget):
    # Signals
    selection_changed = Signal(list)     # Emits list of selected model names (checked ones)
    model_focused = Signal(ModelPricing)  # Emits current highlighted model to editor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_models = []
        self.filtered_models = []
        self.checked_models = set()
        self._site_name = ""
        self._updating_table = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Title
        self.title_lbl = QLabel("模型价格列表")
        self.title_lbl.setObjectName("panelTitle")
        layout.addWidget(self.title_lbl)

        # Search and Selection Controls Layout
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索模型名称...")
        self.search_input.textChanged.connect(self.apply_filter)
        search_layout.addWidget(self.search_input)

        self.select_all_cb = QCheckBox("全选")
        self.select_all_cb.stateChanged.connect(self.on_select_all_toggled)
        search_layout.addWidget(self.select_all_cb)

        layout.addLayout(search_layout)

        # Filter Tabs (using QTabBar for clean, tabbed filter view)
        self.filter_bar = QTabBar()
        self.filter_bar.addTab("全部")
        self.filter_bar.addTab("⚠️ 未设置")
        self.filter_bar.addTab("按量")
        self.filter_bar.addTab("按次")
        self.filter_bar.addTab("表达式")
        self.filter_bar.currentChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["选择", "模型名称", "计费模式", "价格摘要", "状态", "来源站点"])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_row_focused)
        
        layout.addWidget(self.table)

    def set_models(self, models: list, site_name: str = ""):
        self.all_models = models
        self._site_name = site_name
        if site_name:
            self.title_lbl.setText(f"模型价格列表 — {site_name}")
        else:
            self.title_lbl.setText("模型价格列表")
        # Retain checked state if models exist in the new list, else clear
        new_names = {m.name for m in models}
        self.checked_models = self.checked_models.intersection(new_names)
        self.apply_filter()

    def apply_filter(self):
        if self._updating_table:
            return
            
        search_txt = self.search_input.text().strip().lower()
        filter_idx = self.filter_bar.currentIndex()
        
        # Apply filters
        self.filtered_models = []
        for model in self.all_models:
            # 1. Search text filter
            if search_txt and search_txt not in model.name.lower():
                continue
                
            # 2. Tab Category filter
            # Tabs: 0: 全部, 1: 未设置, 2: 按量, 3: 按次, 4: 表达式
            if filter_idx == 1 and model.billing_mode != "unset":
                continue
            elif filter_idx == 2 and model.billing_mode != "quota":
                continue
            elif filter_idx == 3 and model.billing_mode != "times":
                continue
            elif filter_idx == 4 and model.billing_mode != "expr":
                continue
                
            self.filtered_models.append(model)
            
        self.update_table_view()

    def update_table_view(self):
        self._updating_table = True
        self.table.setRowCount(len(self.filtered_models))
        
        for idx, model in enumerate(self.filtered_models):
            # Checkbox in column 0
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_state = Qt.CheckState.Checked if model.name in self.checked_models else Qt.CheckState.Unchecked
            cb_item.setCheckState(check_state)
            self.table.setItem(idx, 0, cb_item)

            # Model Name
            name_item = QTableWidgetItem(model.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # Billing Mode
            mode_display = "未设置"
            if model.billing_mode == "quota":
                mode_display = "按量"
            elif model.billing_mode == "times":
                mode_display = "按次"
            elif model.billing_mode == "expr":
                mode_display = "表达式"
            
            mode_item = QTableWidgetItem(mode_display)
            mode_item.setFlags(mode_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Price Summary
            summary_item = QTableWidgetItem(model.get_summary())
            summary_item.setFlags(summary_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Status
            status_text = "已同步"
            status_color = "#94a3b8"
            if model.status == "modified":
                status_text = "已修改"
                status_color = "#38bdf8"
            elif model.status == "new":
                status_text = "新模型"
                status_color = "#10b981"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # 来源站点 (column 5)
            site_item = QTableWidgetItem(self._site_name)
            site_item.setFlags(site_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            site_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Highlighting for unset models
            if model.billing_mode == "unset":
                warning_color = "#f59e0b"
                name_item.setForeground(QColor(warning_color))
                mode_item.setForeground(QColor(warning_color))
                summary_item.setForeground(QColor(warning_color))
                # Soft dark amber background highlight for the summary cell
                summary_item.setBackground(QColor("#2a1b0a"))

            self.table.setItem(idx, 1, name_item)
            self.table.setItem(idx, 2, mode_item)
            self.table.setItem(idx, 3, summary_item)
            self.table.setItem(idx, 4, status_item)
            self.table.setItem(idx, 5, site_item)

        # Wire check box change
        self.table.itemChanged.connect(self.on_item_changed)
        self._updating_table = False
        
        # Auto-update select all checkbox state
        self.sync_select_all_checkbox_state()

    def on_item_changed(self, item: QTableWidgetItem):
        if self._updating_table:
            return
            
        if item.column() == 0:
            row = item.row()
            if row < len(self.filtered_models):
                model_name = self.filtered_models[row].name
                if item.checkState() == Qt.CheckState.Checked:
                    self.checked_models.add(model_name)
                else:
                    self.checked_models.discard(model_name)
                self.selection_changed.emit(list(self.checked_models))
                self.sync_select_all_checkbox_state()

    def on_select_all_toggled(self, state: int):
        if self._updating_table:
            return
            
        self._updating_table = True
        is_checked = (state == Qt.CheckState.Checked.value)
        
        for idx in range(self.table.rowCount()):
            cb_item = self.table.item(idx, 0)
            if cb_item:
                cb_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                
            model_name = self.filtered_models[idx].name
            if is_checked:
                self.checked_models.add(model_name)
            else:
                self.checked_models.discard(model_name)
                
        self._updating_table = False
        self.selection_changed.emit(list(self.checked_models))

    def sync_select_all_checkbox_state(self):
        if not self.filtered_models:
            self.select_all_cb.setChecked(False)
            return
            
        all_checked = True
        for m in self.filtered_models:
            if m.name not in self.checked_models:
                all_checked = False
                break
                
        self.select_all_cb.blockSignals(True)
        self.select_all_cb.setChecked(all_checked)
        self.select_all_cb.blockSignals(False)

    def on_row_focused(self):
        row = self.table.currentRow()
        if row >= 0 and row < len(self.filtered_models):
            self.model_focused.emit(self.filtered_models[row])

    def get_selected_model_names(self) -> list:
        return list(self.checked_models)
        
    def get_focused_model(self) -> ModelPricing:
        row = self.table.currentRow()
        if row >= 0 and row < len(self.filtered_models):
            return self.filtered_models[row]
        return None
