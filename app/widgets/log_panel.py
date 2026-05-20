from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtCore import Qt, QDateTime

class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header bar
        header_layout = QHBoxLayout()
        title = QLabel("系统日志与同步控制台")
        title.setObjectName("panelTitle")
        header_layout.addWidget(title)
        
        header_layout.addStretch()

        clear_btn = QPushButton("清除日志")
        clear_btn.clicked.connect(self.clear_logs)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # Text Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("logConsole")
        self.console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.console)

        # Initial message
        self.log_info("控制台就绪。等待操作...")

    def _append_log(self, level: str, color: str, message: str):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        html_msg = f"<span style='color: #64748b;'>[{timestamp}]</span> <span style='color: {color}; font-weight: bold;'>[{level}]</span> <span style='color: #f8fafc;'>{message}</span>"
        self.console.append(html_msg)
        # Auto scroll to bottom
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log_info(self, message: str):
        self._append_log("INFO", "#38bdf8", message)

    def log_success(self, message: str):
        self._append_log("SUCCESS", "#10b981", message)

    def log_warning(self, message: str):
        self._append_log("WARN", "#f59e0b", message)

    def log_error(self, message: str):
        self._append_log("ERROR", "#f43f5e", message)

    def clear_logs(self):
        self.console.clear()
        self.log_info("日志已清除。")
