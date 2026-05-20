from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QStackedWidget, QDoubleSpinBox, 
                             QFormLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLineEdit, 
                             QPlainTextEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import Qt, Signal
from ..models import ModelPricing

class PricingEditor(QWidget):
    # Signals
    # Emits selected models list, pricing dictionary
    pricing_applied = Signal(list, dict) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_models = []
        self.focused_model = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Title
        title = QLabel("价格编辑面板")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        # Active Model Info
        self.model_info_lbl = QLabel("未选择模型 (在列表中勾选或点击模型进行编辑)")
        self.model_info_lbl.setObjectName("modelTitle")
        self.model_info_lbl.setWordWrap(True)
        layout.addWidget(self.model_info_lbl)

        # Billing Mode Selector
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("计费模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "未设置价格 (unset)",
            "按量计费 (quota)",
            "按次收费 (times)",
            "表达式 / 阶梯收费 (expr)"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # Stacked Widget for fields
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # 1. Unset Page
        self.unset_page = QWidget()
        unset_layout = QVBoxLayout(self.unset_page)
        unset_lbl = QLabel("当前计费模式为 [未设置价格]\n同步至目标站时将不会做价格更新。")
        unset_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unset_lbl.setStyleSheet("color: #7a8296; font-style: italic;")
        unset_layout.addWidget(unset_lbl)
        self.stacked_widget.addWidget(self.unset_page)

        # 2. Pay-as-you-go (Quota) Page
        self.quota_page = QWidget()
        quota_layout = QFormLayout(self.quota_page)
        quota_layout.setContentsMargins(0, 0, 0, 0)
        quota_layout.setSpacing(8)
        
        self.in_price_spin = QDoubleSpinBox()
        self.in_price_spin.setRange(0, 10000)
        self.in_price_spin.setDecimals(4)
        
        self.out_price_spin = QDoubleSpinBox()
        self.out_price_spin.setRange(0, 10000)
        self.out_price_spin.setDecimals(4)
        
        self.cache_read_spin = QDoubleSpinBox()
        self.cache_read_spin.setRange(0, 10000)
        self.cache_read_spin.setDecimals(4)
        
        self.cache_create_spin = QDoubleSpinBox()
        self.cache_create_spin.setRange(0, 10000)
        self.cache_create_spin.setDecimals(4)
        
        quota_layout.addRow("输入价格 ($/1M tokens):", self.in_price_spin)
        quota_layout.addRow("输出价格 ($/1M tokens):", self.out_price_spin)
        quota_layout.addRow("缓存读取价格 ($/1M tokens):", self.cache_read_spin)
        quota_layout.addRow("缓存创建价格 ($/1M tokens):", self.cache_create_spin)
        
        self.stacked_widget.addWidget(self.quota_page)

        # 3. Pay-per-use (Times) Page
        self.times_page = QWidget()
        times_layout = QFormLayout(self.times_page)
        times_layout.setContentsMargins(0, 0, 0, 0)
        
        self.times_price_spin = QDoubleSpinBox()
        self.times_price_spin.setRange(0, 10000)
        self.times_price_spin.setDecimals(4)
        
        times_layout.addRow("每次调用价格 ($/次):", self.times_price_spin)
        self.stacked_widget.addWidget(self.times_page)

        # 4. Expression / Tiered Page
        self.expr_page = QWidget()
        expr_layout = QVBoxLayout(self.expr_page)
        expr_layout.setContentsMargins(0, 0, 0, 0)
        expr_layout.setSpacing(8)

        # Tiered Section
        tier_group = QGroupBox("可视化阶梯配置")
        tier_group_layout = QVBoxLayout(tier_group)
        tier_group_layout.setContentsMargins(6, 6, 6, 6)

        self.tier_table = QTableWidget()
        self.tier_table.setColumnCount(3)
        self.tier_table.setHorizontalHeaderLabels(["区间起点(Tokens)", "区间终点(Tokens)", "单价 ($)"])
        self.tier_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tier_table.setFixedHeight(120)
        tier_group_layout.addWidget(self.tier_table)

        tier_btn_layout = QHBoxLayout()
        add_tier_btn = QPushButton("添加阶梯")
        add_tier_btn.clicked.connect(self.add_tier_row)
        del_tier_btn = QPushButton("删除阶梯")
        del_tier_btn.setObjectName("dangerBtn")
        del_tier_btn.setEnabled(False)
        del_tier_btn.setToolTip("删除操作已禁用。")
        del_tier_btn.clicked.connect(self.delete_tier_row)
        
        tier_btn_layout.addWidget(add_tier_btn)
        tier_btn_layout.addWidget(del_tier_btn)
        tier_group_layout.addLayout(tier_btn_layout)
        
        expr_layout.addWidget(tier_group)

        # Expression Section
        expr_group = QGroupBox("高级表达式编辑器")
        expr_group_layout = QVBoxLayout(expr_group)
        expr_group_layout.setContentsMargins(6, 6, 6, 6)
        
        self.expr_input = QLineEdit()
        self.expr_input.setPlaceholderText("例如: if (tokens < 1000) 0.05 else 0.03")
        self.expr_input.textChanged.connect(self.update_expression_preview)
        expr_group_layout.addWidget(self.expr_input)

        expr_group_layout.addWidget(QLabel("表达式语义预览:"))
        self.expr_preview = QLabel("未配置表达式")
        self.expr_preview.setWordWrap(True)
        self.expr_preview.setStyleSheet("color: #00e5ff; font-family: monospace; background-color: #0e1014; padding: 6px; border-radius: 4px;")
        expr_group_layout.addWidget(self.expr_preview)

        expr_layout.addWidget(expr_group)
        self.stacked_widget.addWidget(self.expr_page)

        # Save Button
        self.save_btn = QPushButton("💾 保存修改并应用")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.on_apply_clicked)
        layout.addWidget(self.save_btn)

    def on_mode_changed(self, index: int):
        self.stacked_widget.setCurrentIndex(index)

    def set_focused_model(self, model: ModelPricing):
        self.focused_model = model
        self.model_info_lbl.setText(f"当前编辑: {model.name}")
        
        # Load values
        if model.billing_mode == "unset":
            self.mode_combo.setCurrentIndex(0)
        elif model.billing_mode == "quota":
            self.mode_combo.setCurrentIndex(1)
            self.in_price_spin.setValue(model.input_price)
            self.out_price_spin.setValue(model.output_price)
            self.cache_read_spin.setValue(model.cache_read_price)
            self.cache_create_spin.setValue(model.cache_create_price)
        elif model.billing_mode == "times":
            self.mode_combo.setCurrentIndex(2)
            self.times_price_spin.setValue(model.times_price)
        elif model.billing_mode == "expr":
            self.mode_combo.setCurrentIndex(3)
            self.expr_input.setText(model.expression)
            
            # Load Tiers
            self.tier_table.setRowCount(0)
            for tier in model.tiers:
                row = self.tier_table.rowCount()
                self.tier_table.insertRow(row)
                self.tier_table.setItem(row, 0, QTableWidgetItem(str(tier.get("range_start", 0))))
                
                end_val = tier.get("range_end", -1)
                end_str = "∞" if end_val == -1 or end_val == 0 and row > 0 else str(end_val)
                self.tier_table.setItem(row, 1, QTableWidgetItem(end_str))
                
                self.tier_table.setItem(row, 2, QTableWidgetItem(str(tier.get("price", 0.0))))
            
            self.update_expression_preview()

    def set_selected_models(self, model_names: list):
        self.selected_models = model_names
        if len(model_names) > 1:
            self.model_info_lbl.setText(f"当前编辑: 批量选中了 {len(model_names)} 个模型")
        elif len(model_names) == 1:
            # Load that single model if focused
            pass
        else:
            if self.focused_model:
                self.model_info_lbl.setText(f"当前编辑: {self.focused_model.name}")
            else:
                self.model_info_lbl.setText("未选择模型 (在列表中勾选或点击模型进行编辑)")

    def add_tier_row(self):
        row = self.tier_table.rowCount()
        self.tier_table.insertRow(row)
        
        # Smart defaults based on previous tier
        start_val = 0
        if row > 0:
            prev_end = self.tier_table.item(row-1, 1).text()
            if prev_end.isdigit():
                start_val = int(prev_end) + 1
        
        self.tier_table.setItem(row, 0, QTableWidgetItem(str(start_val)))
        self.tier_table.setItem(row, 1, QTableWidgetItem("∞"))
        self.tier_table.setItem(row, 2, QTableWidgetItem("0.0"))
        
        # If we added a tier, auto update preview description
        self.update_expression_preview()

    def delete_tier_row(self):
        QMessageBox.information(self, "删除已禁用", "当前版本禁止删除阶梯配置。")

    def update_expression_preview(self):
        mode_idx = self.mode_combo.currentIndex()
        if mode_idx != 3:
            return
            
        preview_text = ""
        
        # Build description of tiers
        tiers = self.get_tiers_data()
        if tiers:
            preview_text += "阶梯逻辑:\n"
            for t in tiers:
                end_str = "+∞" if t["range_end"] == -1 else f"{t['range_end']}"
                preview_text += f"  • {t['range_start']} 到 {end_str} Tokens => ${t['price']}/Token\n"
        
        expr = self.expr_input.text().strip()
        if expr:
            if preview_text:
                preview_text += "\n"
            preview_text += f"高级公式:\n  {expr}"
            
        if not preview_text:
            preview_text = "未配置表达式或阶梯价格"
            
        self.expr_preview.setText(preview_text)

    def get_tiers_data(self) -> list:
        tiers = []
        for r in range(self.tier_table.rowCount()):
            start_item = self.tier_table.item(r, 0)
            end_item = self.tier_table.item(r, 1)
            price_item = self.tier_table.item(r, 2)
            
            if start_item and end_item and price_item:
                try:
                    start_val = int(start_item.text())
                    
                    end_text = end_item.text().strip()
                    end_val = -1 if end_text in ["∞", "-1", "+∞"] else int(end_text)
                    
                    price_val = float(price_item.text())
                    
                    tiers.append({
                        "range_start": start_val,
                        "range_end": end_val,
                        "price": price_val
                    })
                except ValueError:
                    pass
        return tiers

    def on_apply_clicked(self):
        # We need either a focused model or selected check models
        models_to_apply = []
        if self.selected_models:
            models_to_apply = self.selected_models
        elif self.focused_model:
            models_to_apply = [self.focused_model.name]
            
        if not models_to_apply:
            QMessageBox.information(self, "提示", "请先在列表中选择或勾选需要应用价格的模型。")
            return
            
        mode_map = ["unset", "quota", "times", "expr"]
        selected_mode = mode_map[self.mode_combo.currentIndex()]
        if selected_mode == "unset":
            QMessageBox.warning(self, "删除已禁用", "不能把模型价格保存为未设置状态。")
            return
        
        pricing_data = {
            "billing_mode": selected_mode,
            "input_price": self.in_price_spin.value() if selected_mode == "quota" else 0.0,
            "output_price": self.out_price_spin.value() if selected_mode == "quota" else 0.0,
            "cache_read_price": self.cache_read_spin.value() if selected_mode == "quota" else 0.0,
            "cache_create_price": self.cache_create_spin.value() if selected_mode == "quota" else 0.0,
            "times_price": self.times_price_spin.value() if selected_mode == "times" else 0.0,
            "expression": self.expr_input.text().strip() if selected_mode == "expr" else "",
            "tiers": self.get_tiers_data() if selected_mode == "expr" else []
        }
        
        # Verify correctness for expression mode
        if selected_mode == "expr" and not pricing_data["expression"] and not pricing_data["tiers"]:
            QMessageBox.warning(self, "输入错误", "阶梯配置与公式编辑器不能同时为空！")
            return
            
        self.pricing_applied.emit(models_to_apply, pricing_data)
