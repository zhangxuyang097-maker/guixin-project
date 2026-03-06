"""仿真部件模块.

提供协议仿真和可视化的专用部件。
"""

from typing import Optional, Any, Callable
import asyncio

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QGroupBox,
    QTextEdit, QTreeWidget, QTreeWidgetItem,
    QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor

from core.simulation_engine import (
    SimulationEngine, SimulationNode, SimulationEvent,
    SimulationConfig, ProtocolSimulationBuilder
)
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIConfig


class SimulationWorker(QThread):
    """仿真工作线程.
    
    在后台执行仿真任务。
    """
    
    event_received = pyqtSignal(object)
    simulation_completed = pyqtSignal()
    
    def __init__(
        self,
        protocol_type: str,
        node_count: int,
        duration_ms: float
    ) -> None:
        """初始化仿真工作线程.
        
        Args:
            protocol_type: 协议类型
            node_count: 节点数量
            duration_ms: 仿真时长（毫秒）
        """
        super().__init__()
        self.protocol_type = protocol_type
        self.node_count = node_count
        self.duration_ms = duration_ms
        self._running = False
        self.engine: Optional[SimulationEngine] = None
    
    def run(self) -> None:
        """执行仿真任务."""
        self._running = True
        
        try:
            # 创建仿真构建器
            builder = ProtocolSimulationBuilder()
            
            # 添加节点
            for i in range(self.node_count):
                if self.protocol_type == "RSSP-I":
                    config = RSSPIConfig(node_id=i + 1)
                    protocol = RSSPIProtocol(config)
                else:
                    config = RSSPIIConfig(node_id=i + 1)
                    protocol = RSSPIIProtocol(config)
                
                node_id = builder.add_protocol_node(protocol)
                
                # 设置事件处理器
                if hasattr(protocol, 'set_event_handler'):
                    protocol.set_event_handler(
                        lambda e, nid=node_id: self._on_protocol_event(e, nid)
                    )
            
            # 连接节点（假设是星型拓扑）
            for i in range(1, self.node_count):
                builder.connect_nodes(1, i + 1)
            
            # 构建并运行仿真
            self.engine = builder.build()
            
            # 运行仿真
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.engine.run())
            
        except Exception as e:
            print(f"仿真错误: {e}")
        
        self._running = False
        self.simulation_completed.emit()
    
    def _on_protocol_event(self, event: Any, node_id: int) -> None:
        """处理协议事件.
        
        Args:
            event: 协议事件
            node_id: 节点 ID
        """
        self.event_received.emit({
            "node_id": node_id,
            "event": event,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    def stop(self) -> None:
        """停止仿真."""
        self._running = False
        if self.engine:
            self.engine.stop()
        self.wait(1000)


class SimulationWidget(QWidget):
    """仿真部件类.
    
    提供协议仿真配置、执行和可视化。
    
    Signals:
        simulation_started: 仿真开始信号
        simulation_completed: 仿真完成信号
    """
    
    simulation_started = pyqtSignal()
    simulation_completed = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """初始化仿真部件.
        
        Args:
            parent: 父部件
        """
        super().__init__(parent)
        
        self._setup_ui()
        
        self.simulation_worker: Optional[SimulationWorker] = None
        self._event_count = 0
        
        # 定时器用于更新统计
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_statistics)
    
    def _setup_ui(self) -> None:
        """设置用户界面."""
        layout = QVBoxLayout(self)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 上部 - 控制和状态
        top_panel = self._create_top_panel()
        splitter.addWidget(top_panel)
        
        # 下部 - 事件日志
        bottom_panel = self._create_bottom_panel()
        splitter.addWidget(bottom_panel)
        
        # 设置分割比例
        splitter.setSizes([300, 500])
    
    def _create_top_panel(self) -> QWidget:
        """创建上部面板.
        
        Returns:
            上部面板部件
        """
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # 左侧配置
        config_widget = self._create_config_widget()
        layout.addWidget(config_widget)
        
        # 右侧状态
        status_widget = self._create_status_widget()
        layout.addWidget(status_widget)
        
        return panel
    
    def _create_config_widget(self) -> QWidget:
        """创建配置部件.
        
        Returns:
            配置部件
        """
        panel = QGroupBox("仿真配置")
        layout = QVBoxLayout(panel)
        
        # 协议选择
        protocol_layout = QHBoxLayout()
        protocol_layout.addWidget(QLabel("协议:"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("RSSP-I", "RSSP-I")
        self.protocol_combo.addItem("RSSP-II", "RSSP-II")
        protocol_layout.addWidget(self.protocol_combo)
        layout.addLayout(protocol_layout)
        
        # 节点数量
        node_layout = QHBoxLayout()
        node_layout.addWidget(QLabel("节点数:"))
        self.node_spin = QSpinBox()
        self.node_spin.setRange(2, 10)
        self.node_spin.setValue(2)
        node_layout.addWidget(self.node_spin)
        layout.addLayout(node_layout)
        
        # 仿真时长
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("时长(秒):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setValue(5)
        duration_layout.addWidget(self.duration_spin)
        layout.addLayout(duration_layout)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始仿真")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.start_button.clicked.connect(self._on_start_simulation)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_simulation)
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
    
    def _create_status_widget(self) -> QWidget:
        """创建状态部件.
        
        Returns:
            状态部件
        """
        panel = QGroupBox("仿真状态")
        layout = QVBoxLayout(panel)
        
        # 状态树
        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderLabels(["项目", "值"])
        self.status_tree.setColumnCount(2)
        layout.addWidget(self.status_tree)
        
        # 初始化状态项
        self._init_status_tree()
        
        return panel
    
    def _init_status_tree(self) -> None:
        """初始化状态树."""
        self.status_tree.clear()
        
        self.status_items = {
            "status": QTreeWidgetItem(self.status_tree, ["状态", "空闲"]),
            "node_count": QTreeWidgetItem(self.status_tree, ["节点数", "0"]),
            "event_count": QTreeWidgetItem(self.status_tree, ["事件数", "0"]),
            "duration": QTreeWidgetItem(self.status_tree, ["运行时间", "0s"]),
        }
        
        self.status_tree.expandAll()
    
    def _create_bottom_panel(self) -> QWidget:
        """创建底部面板.
        
        Returns:
            底部面板部件
        """
        panel = QGroupBox("事件日志")
        layout = QVBoxLayout(panel)
        
        # 事件表格
        self.event_table = QTableWidget()
        self.event_table.setColumnCount(4)
        self.event_table.setHorizontalHeaderLabels([
            "时间", "节点", "类型", "详情"
        ])
        self.event_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.event_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.event_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self.event_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.event_table.setColumnWidth(0, 100)
        self.event_table.setColumnWidth(1, 60)
        self.event_table.setColumnWidth(2, 120)
        layout.addWidget(self.event_table)
        
        # 日志文本
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        return panel
    
    def _on_start_simulation(self) -> None:
        """开始仿真按钮点击处理."""
        protocol_type = self.protocol_combo.currentData()
        node_count = self.node_spin.value()
        duration_ms = self.duration_spin.value() * 1000
        
        # 更新 UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.event_table.setRowCount(0)
        self._event_count = 0
        
        # 更新状态
        self.status_items["status"].setText(1, "运行中")
        self.status_items["node_count"].setText(1, str(node_count))
        
        # 创建工作线程
        self.simulation_worker = SimulationWorker(
            protocol_type, node_count, duration_ms
        )
        self.simulation_worker.event_received.connect(self._on_event_received)
        self.simulation_worker.simulation_completed.connect(self._on_simulation_completed)
        self.simulation_worker.start()
        
        # 启动统计定时器
        self._stats_timer.start(500)
        
        self.simulation_started.emit()
    
    def _on_stop_simulation(self) -> None:
        """停止仿真按钮点击处理."""
        if self.simulation_worker:
            self.simulation_worker.stop()
            self.simulation_worker = None
        
        self._stats_timer.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_items["status"].setText(1, "已停止")
        
        self.simulation_completed.emit()
    
    def _on_event_received(self, event_data: dict) -> None:
        """事件接收处理.
        
        Args:
            event_data: 事件数据
        """
        self._event_count += 1
        
        row = self.event_table.rowCount()
        self.event_table.insertRow(row)
        
        # 时间
        timestamp = f"{event_data['timestamp']:.3f}"
        self.event_table.setItem(row, 0, QTableWidgetItem(timestamp))
        
        # 节点
        node_id = str(event_data['node_id'])
        self.event_table.setItem(row, 1, QTableWidgetItem(node_id))
        
        # 类型
        event = event_data['event']
        event_type = "未知"
        details = ""
        
        if hasattr(event, 'msg_type'):
            event_type = event.msg_type.name if hasattr(event.msg_type, 'name') else str(event.msg_type)
            details = f"Seq: {event.sequence_number}"
        elif isinstance(event, dict):
            event_type = event.get('type', '未知')
            details = str(event.get('data', ''))
        
        self.event_table.setItem(row, 2, QTableWidgetItem(event_type))
        self.event_table.setItem(row, 3, QTableWidgetItem(details))
        
        # 滚动到底部
        self.event_table.scrollToBottom()
        
        # 更新日志
        self._log(f"Node {node_id}: {event_type} - {details}")
    
    def _on_simulation_completed(self) -> None:
        """仿真完成处理."""
        self._stats_timer.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)
        self.status_items["status"].setText(1, "完成")
        
        self._log("仿真完成")
        
        self.simulation_completed.emit()
    
    def _update_statistics(self) -> None:
        """更新统计信息."""
        self.status_items["event_count"].setText(1, str(self._event_count))
        
        # 更新进度条（模拟）
        current = self.progress_bar.value()
        if current < 90:
            self.progress_bar.setValue(current + 1)
    
    def _log(self, message: str) -> None:
        """记录日志.
        
        Args:
            message: 日志消息
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def get_statistics(self) -> dict[str, Any]:
        """获取仿真统计信息.
        
        Returns:
            统计信息字典
        """
        return {
            "event_count": self._event_count,
            "node_count": self.node_spin.value(),
            "protocol": self.protocol_combo.currentData(),
        }
