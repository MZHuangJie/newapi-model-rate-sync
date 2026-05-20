from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QPushButton, 
                             QHeaderView, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class SyncPreviewDialog(QDialog):
    def __init__(self, parent=None, plan: list = None):
        super().__init__(parent)
        self.plan = plan or []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("同步方案预览")
        self.resize(750, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Overview Header
        summary_lbl = QLabel(f"本次同步将把源站价格复制到选中的目标站点。共生成了 {len(self.plan)} 项修改项。")
        summary_lbl.setObjectName("modelTitle")
        layout.addWidget(summary_lbl)

        # Comparison Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["目标站点", "模型名称", "当前价格", "同步后价格", "变更状态"])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self.table)

        self.populate_table()

        # Legend / Tip
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("状态说明: "))
        
        create_lbl = QLabel("🟢 新增配置")
        create_lbl.setStyleSheet("color: #39ff14; font-weight: bold; margin-right: 15px;")
        legend_layout.addWidget(create_lbl)
        
        update_lbl = QLabel("🔵 更新价格")
        update_lbl.setStyleSheet("color: #00e5ff; font-weight: bold; margin-right: 15px;")
        legend_layout.addWidget(update_lbl)
        
        nochange_lbl = QLabel("⚪ 无变化")
        nochange_lbl.setStyleSheet("color: #7a8296; font-weight: bold;")
        legend_layout.addWidget(nochange_lbl)

        blocked_lbl = QLabel("⛔ 已阻止")
        blocked_lbl.setStyleSheet("color: #f59e0b; font-weight: bold; margin-left: 15px;")
        legend_layout.addWidget(blocked_lbl)
        
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #2d3345;")
        layout.addWidget(line)

        # Buttons
        btn_layout = QHBoxLayout()
        self.confirm_btn = QPushButton("🚀 确认并执行同步")
        self.confirm_btn.setObjectName("primaryBtn")
        self.confirm_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

    def populate_table(self):
        self.table.setRowCount(len(self.plan))
        
        for idx, item in enumerate(self.plan):
            tgt_site_item = QTableWidgetItem(item["target_site_name"])
            model_item = QTableWidgetItem(item["model_name"])
            old_price_item = QTableWidgetItem(item["target_summary"])
            new_price_item = QTableWidgetItem(item["source_summary"])
            
            # Action formatting
            action = item["action"]
            action_text = "未知"
            action_color = "#f8fafc"
            
            if action == "CREATE":
                action_text = "🟢 新增"
                action_color = "#10b981"
            elif action == "UPDATE":
                action_text = "🔵 更新"
                action_color = "#38bdf8"
            elif action == "NO_CHANGE":
                action_text = "⚪ 无变化"
                action_color = "#94a3b8"
            elif action == "BLOCKED":
                action_text = "⛔ 已阻止"
                action_color = "#f59e0b"
                new_price_item.setText(item.get("block_reason", item["source_summary"]))
                
            action_item = QTableWidgetItem(action_text)
            action_item.setForeground(QColor(action_color))
            action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Read-only
            for i in (tgt_site_item, model_item, old_price_item, new_price_item, action_item):
                i.setFlags(i.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(idx, 0, tgt_site_item)
            self.table.setItem(idx, 1, model_item)
            self.table.setItem(idx, 2, old_price_item)
            self.table.setItem(idx, 3, new_price_item)
            self.table.setItem(idx, 4, action_item)
            
            # Highlight backgrounds slightly depending on severity
            if action == "CREATE":
                for col in range(5):
                    self.table.item(idx, col).setBackground(QColor("#062f21"))
            elif action == "UPDATE":
                # Subtle slate tint or default
                pass
            elif action == "NO_CHANGE":
                # Make text slightly lighter/muted
                for col in range(5):
                    self.table.item(idx, col).setForeground(QColor("#64748b"))
            elif action == "BLOCKED":
                for col in range(5):
                    self.table.item(idx, col).setBackground(QColor("#2a1b0a"))
