from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QPushButton, QFrame, QMessageBox, QDialog)
from PySide6.QtCore import Qt, QThread, Signal

from .widgets.site_panel import SitePanel
from .widgets.model_table import ModelTable
from .widgets.pricing_editor import PricingEditor
from .widgets.log_panel import LogPanel
from .widgets.sync_preview_dialog import SyncPreviewDialog
from . import api_bridge
from .models import Site, ModelPricing

# Generic Worker for simple async calls
class ActionWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


# Specialized Sync Worker to stream logs line-by-line
class SyncWorker(QThread):
    log_emitted = Signal(str, str)     # level, message
    progress_finished = Signal(dict)   # final stats
    error = Signal(str)

    def __init__(self, plan):
        super().__init__()
        self.plan = plan

    def run(self):
        try:
            self.log_emitted.emit("INFO", "开始执行跨站点价格同步...")
            result = api_bridge.execute_sync(self.plan)
            for line in result.get("logs", []):
                if "失败" in line:
                    level = "ERROR"
                elif "阻止" in line or "禁用" in line:
                    level = "WARN"
                elif "成功" in line or "结束" in line:
                    level = "SUCCESS"
                else:
                    level = "INFO"
                self.log_emitted.emit(level, line)
            self.progress_finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NewAPI 多个站点模型价格一键同步工具")
        self.resize(1200, 750)
        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Upper Layout: Three Column Panels using QSplitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 1. Left Panel (Site Management)
        self.site_panel = SitePanel()
        self.site_panel.setObjectName("panelFrame")
        # Wrap in a QFrame for styling border in QSS
        site_frame = QFrame()
        site_frame.setObjectName("panelFrame")
        sf_layout = QVBoxLayout(site_frame)
        sf_layout.addWidget(self.site_panel)
        splitter.addWidget(site_frame)

        # 2. Middle Panel (Models list)
        self.model_table = ModelTable()
        model_frame = QFrame()
        model_frame.setObjectName("panelFrame")
        mf_layout = QVBoxLayout(model_frame)
        mf_layout.addWidget(self.model_table)
        splitter.addWidget(model_frame)

        # 3. Right Panel (Pricing Edit Editor)
        self.pricing_editor = PricingEditor()
        editor_frame = QFrame()
        editor_frame.setObjectName("panelFrame")
        ef_layout = QVBoxLayout(editor_frame)
        ef_layout.addWidget(self.pricing_editor)
        splitter.addWidget(editor_frame)

        # Set ratio widths: 30% : 40% : 30%
        splitter.setSizes([350, 480, 370])
        main_layout.addWidget(splitter, stretch=3)

        # Bottom Bar: Sync Control & Log Console
        bottom_frame = QFrame()
        bottom_frame.setObjectName("panelFrame")
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(6)

        # Large Sync button and logs
        sync_control_layout = QHBoxLayout()
        self.sync_now_btn = QPushButton("🚀 一键同步所选价格 (从源站同步到目标站)")
        self.sync_now_btn.setObjectName("primaryBtn")
        self.sync_now_btn.setStyleSheet("font-size: 14px; padding: 10px 20px;")
        self.sync_now_btn.clicked.connect(self.start_sync_flow)
        sync_control_layout.addWidget(self.sync_now_btn)
        bottom_layout.addLayout(sync_control_layout)

        self.log_panel = LogPanel()
        bottom_layout.addWidget(self.log_panel)
        
        main_layout.addWidget(bottom_frame, stretch=1)

        # Connect signals
        self.site_panel.source_changed.connect(self.on_source_site_changed)
        self.site_panel.site_add_requested.connect(self.on_site_add)
        self.site_panel.site_edit_requested.connect(self.on_site_edit)
        self.site_panel.site_delete_requested.connect(self.on_site_delete)
        self.site_panel.test_connection_requested.connect(self.on_test_site_connection)
        
        self.model_table.model_focused.connect(self.pricing_editor.set_focused_model)
        self.model_table.selection_changed.connect(self.pricing_editor.set_selected_models)
        
        self.pricing_editor.pricing_applied.connect(self.on_pricing_applied)

    def load_initial_data(self):
        self.log_panel.log_info("正在获取站点列表...")
        self.worker = ActionWorker(api_bridge.list_sites)
        self.worker.finished.connect(self.on_sites_loaded)
        self.worker.error.connect(lambda err: self.log_panel.log_error(f"获取站点失败: {err}"))
        self.worker.start()

    # --- Site Actions ---
    def on_sites_loaded(self, sites):
        self.site_panel.set_sites(sites)
        self.log_panel.log_info(f"成功加载了 {len(sites)} 个站点配置。")

    def on_source_site_changed(self, site_id):
        site = next((s for s in self.site_panel.sites if s.id == site_id), None)
        if not site:
            return
            
        self._current_source_site_name = site.name
        self.log_panel.log_info(f"选择源站: '{site.name}'，正在加载该站点的模型价格...")
        
        # Load models for this source site in background
        self.load_models_worker = ActionWorker(api_bridge.load_site_models, site_id)
        self.load_models_worker.finished.connect(self.on_models_loaded)
        self.load_models_worker.error.connect(lambda err: self.log_panel.log_error(f"加载模型价格失败: {err}"))
        self.load_models_worker.start()

    def on_models_loaded(self, models):
        self.model_table.set_models(models, site_name=self._current_source_site_name)
        # Clear selected models cache
        self.pricing_editor.set_selected_models([])
        self.log_panel.log_success(f"成功加载模型价格列表，共计 {len(models)} 个模型。")

    def on_site_add(self, data):
        self.log_panel.log_info(f"正在保存新站点 '{data['name']}'...")
        self.add_worker = ActionWorker(api_bridge.add_site, data)
        self.add_worker.finished.connect(self.on_site_add_done)
        self.add_worker.start()

    def on_site_add_done(self, site):
        self.log_panel.log_success(f"站点 '{site.name}' 添加成功！")
        self.load_initial_data()

    def on_site_edit(self, site_id, data):
        self.log_panel.log_info(f"正在保存修改...")
        self.edit_worker = ActionWorker(api_bridge.edit_site, site_id, data)
        self.edit_worker.finished.connect(lambda _: self.on_site_edit_done(data['name']))
        self.edit_worker.start()

    def on_site_edit_done(self, name):
        self.log_panel.log_success(f"站点 '{name}' 修改已保存！")
        self.load_initial_data()

    def on_site_delete(self, site_id):
        self.log_panel.log_warning("删除操作已被禁用，站点配置不会被删除。")
        QMessageBox.information(self, "删除已禁用", "当前版本禁止删除站点、模型或模型价格。")

    def on_site_delete_done(self, success):
        if success:
            self.log_panel.log_success("站点删除成功。")
            self.load_initial_data()
        else:
            self.log_panel.log_error("站点删除失败。")

    def on_test_site_connection(self, site_id):
        site = next((s for s in self.site_panel.sites if s.id == site_id), None)
        if not site:
            return
            
        self.log_panel.log_info(f"正在测试站点 '{site.name}' ({site.url}) 的网络连通性...")
        self.test_worker = ActionWorker(api_bridge.test_site, site_id)
        
        def handle_test_result(result):
            self.site_panel.update_site_status(site_id, result["status"])
            if result["success"]:
                self.log_panel.log_success(f"站点 '{site.name}' 测试成功: {result['message']}")
                # 测试成功后自动将该站点设为源站，并加载模型价格列表
                if site_id in self.site_panel.source_radio_buttons:
                    self.site_panel.source_radio_buttons[site_id].setChecked(True)
            else:
                self.log_panel.log_error(f"站点 '{site.name}' 测试失败: {result['message']}")
                
        self.test_worker.finished.connect(handle_test_result)
        self.test_worker.start()

    # --- Pricing Editor Actions ---
    def on_pricing_applied(self, model_names, pricing_data):
        source_id = self.site_panel.get_source_site_id()
        if not source_id:
            QMessageBox.warning(self, "操作错误", "请先选择一个源站，加载其价格后再编辑！")
            return
            
        self.log_panel.log_info(f"正在将价格写入本地缓存 ({len(model_names)} 个模型)...")
        if pricing_data.get("billing_mode") == "unset":
            QMessageBox.warning(self, "删除已禁用", "不能把模型价格保存为未设置状态。")
            self.log_panel.log_warning("已阻止清空模型价格。")
            return
        
        blocked_count = 0
        for name in model_names:
            if not api_bridge.update_model_pricing_local(source_id, name, pricing_data):
                blocked_count += 1
            
        if blocked_count:
            self.log_panel.log_warning(f"有 {blocked_count} 个模型被阻止修改。")
        else:
            self.log_panel.log_success(f"本地价格已更新。可勾选目标站进行 [一键同步]。")
        
        # Reload source models to update table view
        self.on_source_site_changed(source_id)

    # --- Sync Flow Actions ---
    def start_sync_flow(self):
        source_id = self.site_panel.get_source_site_id()
        target_ids = self.site_panel.get_target_site_ids()
        selected_models = self.model_table.get_selected_model_names()

        if not source_id:
            QMessageBox.warning(self, "输入校验失败", "请先选择一个源站 (在 '源站' 列勾选单选框)！")
            return
            
        if not target_ids:
            QMessageBox.warning(self, "输入校验失败", "请至少勾选一个目标站！")
            return
            
        if not selected_models:
            QMessageBox.warning(self, "输入校验失败", "请在模型列表中至少勾选一个模型进行同步！")
            return

        self.log_panel.log_info("正在解析各站点差异，生成同步方案预览...")
        self.sync_now_btn.setEnabled(False)
        self.sync_now_btn.setText("正在解析同步数据...")

        # Run preview in background
        self.preview_worker = ActionWorker(api_bridge.preview_sync, source_id, target_ids, selected_models)
        self.preview_worker.finished.connect(self.show_sync_preview_dialog)
        self.preview_worker.error.connect(self.on_sync_error)
        self.preview_worker.start()

    def show_sync_preview_dialog(self, plan):
        self.sync_now_btn.setEnabled(True)
        self.sync_now_btn.setText("🚀 一键同步所选价格 (从源站同步到目标站)")
        
        if not plan:
            QMessageBox.information(self, "提示", "所有选中模型价格在目标站上均已一致，无需同步。")
            return
            
        dialog = SyncPreviewDialog(self, plan)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # User confirmed! Run execution
            self.execute_synchronization(plan)

    def execute_synchronization(self, plan):
        self.sync_now_btn.setEnabled(False)
        self.sync_now_btn.setText("正在执行同步中...")
        
        self.sync_worker = SyncWorker(plan)
        
        # Pipe logs directly to LogPanel in real-time
        def on_log_received(level, msg):
            if level == "INFO":
                self.log_panel.log_info(msg)
            elif level == "SUCCESS":
                self.log_panel.log_success(msg)
            elif level == "ERROR":
                self.log_panel.log_error(msg)
            elif level == "WARN":
                self.log_panel.log_warning(msg)
                
        self.sync_worker.log_emitted.connect(on_log_received)
        self.sync_worker.progress_finished.connect(self.on_sync_completed)
        self.sync_worker.error.connect(self.on_sync_error)
        self.sync_worker.start()

    def on_sync_completed(self, stats):
        self.sync_now_btn.setEnabled(True)
        self.sync_now_btn.setText("🚀 一键同步所选价格 (从源站同步到目标站)")
        blocked = stats.get("blocked_count", 0)
        QMessageBox.information(self, "同步完成", f"价格同步任务已完成！\n成功: {stats['success_count']} 项\n失败: {stats['fail_count']} 项\n阻止: {blocked} 项")
        
        # Refresh current active model pricing view
        source_id = self.site_panel.get_source_site_id()
        if source_id:
            self.on_source_site_changed(source_id)

    def on_sync_error(self, err):
        self.sync_now_btn.setEnabled(True)
        self.sync_now_btn.setText("🚀 一键同步所选价格 (从源站同步到目标站)")
        self.log_panel.log_error(f"同步任务遇到异常: {err}")
        QMessageBox.critical(self, "任务中断", f"操作失败，遇到异常错误:\n{err}")
