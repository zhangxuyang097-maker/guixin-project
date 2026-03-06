"""GUI 主窗口模块.

实现轨芯安工具的主窗口界面。
"""

import sys
from typing import Optional, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QMenuBar, QToolBar, QStatusBar,
    QLabel, QPushButton, QTextEdit, QComboBox,
    QSpinBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QProgressBar, QSplitter,
    QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon, QFont

from core.verification_engine import BMCEngine, VerificationResult, VerificationStatus
from core.verification_scenarios import (
    VerificationScenarios, ScenarioRunner, ProtocolProperties
)
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIConfig


class VerificationWorker(QThread):
    """验证工作线程.
    
    在后台执行验证任务，避免阻塞 GUI。
    """
    
    result_ready = pyqtSignal(object)
    progress_update = pyqtSignal(int, str)
    
    def __init__(
        self,
        scenario_type: str,
        protocol_type: str,
        bound: int = 10
    ) -> None:
        """初始化验证工作线程.
        
        Args:
            scenario_type: 场景类型
            protocol_type: 协议类型
            bound: 验证边界
        """
        super().__init__()
        self.scenario_type = scenario_type
        self.protocol_type = protocol_type
        self.bound = bound
        self._running = False
    
    def run(self) -> None:
        """执行验证任务."""
        self._running = True
        
        try:
            self.progress_update.emit(10, "初始化场景...")
            
            # 创建场景
            if self.scenario_type == "normal":
                scenario = VerificationScenarios.create_normal_operation_scenario(
                    self.protocol_type
                )
            elif self.scenario_type == "replay":
                scenario = VerificationScenarios.create_replay_attack_scenario(
                    self.protocol_type
                )
            elif self.scenario_type == "sequence":
                scenario = VerificationScenarios.create_sequence_error_scenario(
                    self.protocol_type
                )
            elif self.scenario_type == "checksum":
                scenario = VerificationScenarios.create_checksum_error_scenario(
                    self.protocol_type
                )
            elif self.scenario_type == "dual_channel":
                scenario = VerificationScenarios.create_dual_channel_fault_scenario()
            else:
                scenario = VerificationScenarios.create_normal_operation_scenario(
                    self.protocol_type
                )
            
            self.progress_update.emit(30, "执行场景...")
            
            # 运行场景
            runner = ScenarioRunner()
            result = runner.run_scenario(scenario)
            
            self.progress_update.emit(90, "处理结果...")
            
            self.result_ready.emit(result)
            
        except Exception as e:
            self.result_ready.emit(e)
        
        self._running = False
    
    def stop(self) -> None:
        """停止验证任务."""
        self._running = False
        self.wait(1000)


class MainWindow(QMainWindow):
    """主窗口类.
    
    轨芯安工具的主界面，提供验证、仿真和结果展示功能。
    """
    
    def __init__(self) -> None:
        """初始化主窗口."""
        super().__init__()
        
        self.setWindowTitle("轨芯安 (RailCore Secure) - 轨道交通信号安全协议形式化验证工具")
        self.setGeometry(100, 100, 1200, 800)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        
        self.verification_worker: Optional[VerificationWorker] = None
    
    def _setup_ui(self) -> None:
        """设置用户界面."""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板 - 控制区
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板 - 结果展示区
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([400, 800])
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板.
        
        Returns:
            左侧面板部件
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 协议选择组
        protocol_group = QGroupBox("协议选择")
        protocol_layout = QVBoxLayout(protocol_group)
        
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("RSSP-I", "RSSP-I")
        self.protocol_combo.addItem("RSSP-II", "RSSP-II")
        protocol_layout.addWidget(self.protocol_combo)
        
        layout.addWidget(protocol_group)
        
        # 场景选择组
        scenario_group = QGroupBox("验证场景")
        scenario_layout = QVBoxLayout(scenario_group)
        
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem("正常操作", "normal")
        self.scenario_combo.addItem("重放攻击", "replay")
        self.scenario_combo.addItem("序列号错误", "sequence")
        self.scenario_combo.addItem("校验和错误", "checksum")
        self.scenario_combo.addItem("双通道故障", "dual_channel")
        scenario_layout.addWidget(self.scenario_combo)
        
        layout.addWidget(scenario_group)
        
        # 参数设置组
        params_group = QGroupBox("参数设置")
        params_layout = QVBoxLayout(params_group)
        
        # 验证边界
        bound_layout = QHBoxLayout()
        bound_layout.addWidget(QLabel("验证边界:"))
        self.bound_spin = QSpinBox()
        self.bound_spin.setRange(1, 1000)
        self.bound_spin.setValue(10)
        bound_layout.addWidget(self.bound_spin)
        params_layout.addLayout(bound_layout)
        
        layout.addWidget(params_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.run_button = QPushButton("运行验证")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.run_button.clicked.connect(self._on_run_verification)
        button_layout.addWidget(self.run_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_verification)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 添加弹性空间
        layout.addStretch()
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板.
        
        Returns:
            右侧面板部件
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 结果标签页
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        self.tab_widget.addTab(self.result_text, "验证结果")
        
        # 日志标签页
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.tab_widget.addTab(self.log_text, "运行日志")
        
        # 统计标签页
        self.stats_tree = QTreeWidget()
        self.stats_tree.setHeaderLabels(["项目", "值"])
        self.tab_widget.addTab(self.stats_tree, "统计信息")
        
        layout.addWidget(self.tab_widget)
        
        return panel
    
    def _setup_menu(self) -> None:
        """设置菜单栏."""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 验证菜单
        verify_menu = menubar.addMenu("验证")
        
        run_action = QAction("运行验证", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._on_run_verification)
        verify_menu.addAction(run_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self) -> None:
        """设置工具栏."""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        run_action = QAction("运行", self)
        run_action.triggered.connect(self._on_run_verification)
        toolbar.addAction(run_action)
        
        toolbar.addSeparator()
        
        clear_action = QAction("清空", self)
        clear_action.triggered.connect(self._on_clear_results)
        toolbar.addAction(clear_action)
    
    def _setup_statusbar(self) -> None:
        """设置状态栏."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.statusbar.showMessage("就绪")
        
        # 状态标签
        self.status_label = QLabel("状态: 空闲")
        self.statusbar.addPermanentWidget(self.status_label)
    
    def _on_run_verification(self) -> None:
        """运行验证按钮点击处理."""
        protocol_type = self.protocol_combo.currentData()
        scenario_type = self.scenario_combo.currentData()
        bound = self.bound_spin.value()
        
        # 更新 UI
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("状态: 运行中")
        
        # 清空之前的结果
        self.result_text.clear()
        self._log(f"开始验证: {protocol_type} - {scenario_type}")
        
        # 创建工作线程
        self.verification_worker = VerificationWorker(
            scenario_type, protocol_type, bound
        )
        self.verification_worker.result_ready.connect(self._on_verification_complete)
        self.verification_worker.progress_update.connect(self._on_progress_update)
        self.verification_worker.start()
    
    def _on_stop_verification(self) -> None:
        """停止验证按钮点击处理."""
        if self.verification_worker:
            self.verification_worker.stop()
            self.verification_worker = None
        
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("状态: 已停止")
    
    def _on_verification_complete(self, result: Any) -> None:
        """验证完成处理.
        
        Args:
            result: 验证结果或异常
        """
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)
        
        if isinstance(result, Exception):
            self.status_label.setText("状态: 错误")
            self._log(f"验证失败: {result}")
            QMessageBox.critical(self, "错误", f"验证失败: {result}")
        else:
            self.status_label.setText("状态: 完成")
            self._display_result(result)
        
        self.verification_worker = None
    
    def _on_progress_update(self, progress: int, message: str) -> None:
        """进度更新处理.
        
        Args:
            progress: 进度百分比
            message: 进度消息
        """
        self.progress_bar.setValue(progress)
        self._log(message)
    
    def _display_result(self, result: VerificationResult) -> None:
        """显示验证结果.
        
        Args:
            result: 验证结果
        """
        text = f"""
========================================
验证结果
========================================
属性名称: {result.property_name}
验证状态: {result.status.name}
验证边界: {result.bound}
执行时间: {result.time_seconds:.3f} 秒
消息: {result.message}
"""
        
        if result.counter_example:
            text += f"""
反例信息:
  步数: {result.counter_example.step}
  状态: {result.counter_example.state}
"""
        
        if result.solver_stats:
            text += f"""
求解器统计:
  总检查次数: {result.solver_stats.get('total_checks', 'N/A')}
  SAT 结果: {result.solver_stats.get('sat_results', 'N/A')}
  UNSAT 结果: {result.solver_stats.get('unsat_results', 'N/A')}
"""
        
        self.result_text.setText(text)
        self._log("验证完成")
        
        # 更新统计树
        self._update_stats_tree(result)
    
    def _update_stats_tree(self, result: VerificationResult) -> None:
        """更新统计树.
        
        Args:
            result: 验证结果
        """
        self.stats_tree.clear()
        
        root = QTreeWidgetItem(self.stats_tree, ["验证结果", ""])
        
        QTreeWidgetItem(root, ["属性名称", result.property_name])
        QTreeWidgetItem(root, ["验证状态", result.status.name])
        QTreeWidgetItem(root, ["验证边界", str(result.bound)])
        QTreeWidgetItem(root, ["执行时间", f"{result.time_seconds:.3f} 秒"])
        
        self.stats_tree.expandAll()
    
    def _on_clear_results(self) -> None:
        """清空结果按钮点击处理."""
        self.result_text.clear()
        self.log_text.clear()
        self.stats_tree.clear()
        self.progress_bar.setValue(0)
    
    def _on_about(self) -> None:
        """关于菜单点击处理."""
        QMessageBox.about(
            self,
            "关于轨芯安",
            """<h2>轨芯安 (RailCore Secure)</h2>
            <p>版本: 1.0.0</p>
            <p>面向国产 RISC-V 架构的轨道交通信号安全协议形式化验证工具</p>
            <p>支持 RSSP-I/II 协议验证，满足 SIL4 级安全要求</p>
            <p>技术栈: Python 3.9+, Z3 Solver, Asyncio, PyQt6</p>
            """
        )
    
    def _log(self, message: str) -> None:
        """记录日志.
        
        Args:
            message: 日志消息
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event) -> None:
        """窗口关闭事件处理.
        
        Args:
            event: 关闭事件
        """
        if self.verification_worker and self.verification_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "验证任务正在运行，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.verification_worker.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main() -> None:
    """主函数."""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
