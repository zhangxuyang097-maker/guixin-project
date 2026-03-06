"""验证部件模块.

提供验证配置和结果显示的专用部件。
"""

from typing import Optional, Any, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QGroupBox,
    QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.verification_engine import VerificationResult, VerificationStatus


class VerificationWidget(QWidget):
    """验证部件类.
    
    提供验证配置界面和结果展示。
    
    Signals:
        verification_started: 验证开始信号
        verification_completed: 验证完成信号
    """
    
    verification_started = pyqtSignal()
    verification_completed = pyqtSignal(object)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """初始化验证部件.
        
        Args:
            parent: 父部件
        """
        super().__init__(parent)
        
        self._setup_ui()
        self._result_callback: Optional[Callable[[VerificationResult], None]] = None
    
    def _setup_ui(self) -> None:
        """设置用户界面."""
        layout = QHBoxLayout(self)
        
        # 左侧配置面板
        config_panel = self._create_config_panel()
        layout.addWidget(config_panel, 1)
        
        # 右侧结果面板
        result_panel = self._create_result_panel()
        layout.addWidget(result_panel, 2)
    
    def _create_config_panel(self) -> QWidget:
        """创建配置面板.
        
        Returns:
            配置面板部件
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 协议选择
        protocol_group = QGroupBox("协议选择")
        protocol_layout = QVBoxLayout(protocol_group)
        
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("RSSP-I", "RSSP-I")
        self.protocol_combo.addItem("RSSP-II", "RSSP-II")
        protocol_layout.addWidget(self.protocol_combo)
        
        layout.addWidget(protocol_group)
        
        # 验证参数
        params_group = QGroupBox("验证参数")
        params_layout = QVBoxLayout(params_group)
        
        # 验证边界
        bound_layout = QHBoxLayout()
        bound_layout.addWidget(QLabel("验证边界:"))
        self.bound_spin = QSpinBox()
        self.bound_spin.setRange(1, 1000)
        self.bound_spin.setValue(10)
        bound_layout.addWidget(self.bound_spin)
        params_layout.addLayout(bound_layout)
        
        # 超时设置
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("超时(秒):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(30)
        timeout_layout.addWidget(self.timeout_spin)
        params_layout.addLayout(timeout_layout)
        
        # 增量验证
        self.incremental_check = QCheckBox("增量验证")
        self.incremental_check.setChecked(False)
        params_layout.addWidget(self.incremental_check)
        
        layout.addWidget(params_group)
        
        # 属性选择
        property_group = QGroupBox("验证属性")
        property_layout = QVBoxLayout(property_group)
        
        self.sequence_check = QCheckBox("序列号单调性")
        self.sequence_check.setChecked(True)
        property_layout.addWidget(self.sequence_check)
        
        self.replay_check = QCheckBox("防重放")
        self.replay_check.setChecked(True)
        property_layout.addWidget(self.replay_check)
        
        self.checksum_check = QCheckBox("校验和有效性")
        self.checksum_check.setChecked(True)
        property_layout.addWidget(self.checksum_check)
        
        self.window_check = QCheckBox("窗口不变式")
        self.window_check.setChecked(True)
        property_layout.addWidget(self.window_check)
        
        layout.addWidget(property_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.run_button = QPushButton("开始验证")
        self.run_button.clicked.connect(self._on_start_verification)
        button_layout.addWidget(self.run_button)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self._on_clear)
        button_layout.addWidget(self.clear_button)
        
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 添加弹性空间
        layout.addStretch()
        
        return panel
    
    def _create_result_panel(self) -> QWidget:
        """创建结果面板.
        
        Returns:
            结果面板部件
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 结果摘要
        summary_group = QGroupBox("验证摘要")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 10))
        self.summary_text.setMaximumHeight(150)
        summary_layout.addWidget(self.summary_text)
        
        layout.addWidget(summary_group)
        
        # 详细结果表格
        details_group = QGroupBox("详细结果")
        details_layout = QVBoxLayout(details_group)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels([
            "属性名称", "状态", "时间(秒)", "消息"
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        details_layout.addWidget(self.result_table)
        
        layout.addWidget(details_group)
        
        return panel
    
    def _on_start_verification(self) -> None:
        """开始验证按钮点击处理."""
        self.verification_started.emit()
        self.run_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def _on_clear(self) -> None:
        """清空按钮点击处理."""
        self.summary_text.clear()
        self.result_table.setRowCount(0)
        self.progress_bar.setValue(0)
    
    def set_progress(self, progress: int) -> None:
        """设置进度.
        
        Args:
            progress: 进度百分比
        """
        self.progress_bar.setValue(progress)
    
    def add_result(self, result: VerificationResult) -> None:
        """添加验证结果.
        
        Args:
            result: 验证结果
        """
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        
        # 属性名称
        self.result_table.setItem(row, 0, QTableWidgetItem(result.property_name))
        
        # 状态
        status_item = QTableWidgetItem(result.status.name)
        if result.status == VerificationStatus.VERIFIED:
            status_item.setBackground(QColor("#90EE90"))
        elif result.status == VerificationStatus.VIOLATION_FOUND:
            status_item.setBackground(QColor("#FFB6C1"))
        elif result.status == VerificationStatus.ERROR:
            status_item.setBackground(QColor("#FFA500"))
        self.result_table.setItem(row, 1, status_item)
        
        # 时间
        self.result_table.setItem(
            row, 2, QTableWidgetItem(f"{result.time_seconds:.3f}")
        )
        
        # 消息
        self.result_table.setItem(row, 3, QTableWidgetItem(result.message))
        
        # 更新摘要
        self._update_summary(result)
        
        # 恢复按钮
        self.run_button.setEnabled(True)
        
        # 发射完成信号
        self.verification_completed.emit(result)
    
    def _update_summary(self, result: VerificationResult) -> None:
        """更新摘要.
        
        Args:
            result: 验证结果
        """
        summary = f"""
验证结果摘要:
==============
属性: {result.property_name}
状态: {result.status.name}
边界: {result.bound}
时间: {result.time_seconds:.3f} 秒

{result.message}
"""
        self.summary_text.setText(summary)
    
    def get_selected_properties(self) -> list[str]:
        """获取选中的属性列表.
        
        Returns:
            属性名称列表
        """
        properties = []
        
        if self.sequence_check.isChecked():
            properties.append("sequence_monotonicity")
        if self.replay_check.isChecked():
            properties.append("no_replay")
        if self.checksum_check.isChecked():
            properties.append("checksum_validity")
        if self.window_check.isChecked():
            properties.append("window_invariant")
        
        return properties
    
    def get_protocol_type(self) -> str:
        """获取选中的协议类型.
        
        Returns:
            协议类型字符串
        """
        return self.protocol_combo.currentData()
    
    def get_bound(self) -> int:
        """获取验证边界.
        
        Returns:
            验证边界值
        """
        return self.bound_spin.value()
    
    def set_result_callback(self, callback: Callable[[VerificationResult], None]) -> None:
        """设置结果回调函数.
        
        Args:
            callback: 回调函数
        """
        self._result_callback = callback
