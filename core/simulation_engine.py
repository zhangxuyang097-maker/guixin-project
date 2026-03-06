"""并发仿真引擎模块.

基于 Asyncio 实现并发仿真框架，支持多节点协议仿真和时序控制。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, TypeVar
from enum import Enum, auto
from collections.abc import Coroutine
import time

from core.exceptions import TimeoutError, SimulationError


T = TypeVar('T')


class SimulationEventType(Enum):
    """仿真事件类型枚举."""
    
    MESSAGE_SENT = auto()
    MESSAGE_RECEIVED = auto()
    TIMEOUT = auto()
    ERROR = auto()
    STATE_CHANGE = auto()
    CHECKPOINT = auto()


@dataclass
class SimulationEvent:
    """仿真事件数据类.
    
    Attributes:
        event_type: 事件类型
        timestamp: 事件时间戳
        node_id: 相关节点 ID
        data: 事件数据
    """
    
    event_type: SimulationEventType
    timestamp: float
    node_id: int
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationConfig:
    """仿真配置.
    
    Attributes:
        simulation_time_ms: 仿真时长（毫秒）
        time_scale: 时间缩放因子（1.0 为实时）
        max_events: 最大事件数
        enable_logging: 是否启用日志
    """
    
    simulation_time_ms: float = 10000.0
    time_scale: float = 1.0
    max_events: int = 10000
    enable_logging: bool = True


class SimulationNode:
    """仿真节点基类.
    
    表示仿真中的一个协议节点。
    
    Attributes:
        node_id: 节点 ID
        protocol: 协议实例
        message_queue: 消息队列
        event_handler: 事件处理器
    """
    
    def __init__(self, node_id: int, protocol: Any) -> None:
        """初始化仿真节点.
        
        Args:
            node_id: 节点 ID
            protocol: 协议实例
        """
        self.node_id = node_id
        self.protocol = protocol
        self.message_queue: asyncio.Queue[Any] = asyncio.Queue()
        self.event_handler: Optional[Callable[[SimulationEvent], None]] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动节点仿真."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self) -> None:
        """停止节点仿真."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_loop(self) -> None:
        """节点主循环."""
        while self._running:
            try:
                # 检查消息队列
                if not self.message_queue.empty():
                    message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=0.001
                    )
                    await self._handle_message(message)
                
                # 执行协议逻辑
                await self._process_protocol()
                
                # 短暂休眠
                await asyncio.sleep(0.001)
                
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                if self.event_handler:
                    self.event_handler(SimulationEvent(
                        event_type=SimulationEventType.ERROR,
                        timestamp=time.perf_counter(),
                        node_id=self.node_id,
                        data={"error": str(e)}
                    ))
    
    async def _handle_message(self, message: Any) -> None:
        """处理接收到的消息.
        
        Args:
            message: 接收到的消息
        """
        if hasattr(self.protocol, 'receive_message'):
            self.protocol.receive_message(message)
        
        if self.event_handler:
            self.event_handler(SimulationEvent(
                event_type=SimulationEventType.MESSAGE_RECEIVED,
                timestamp=time.perf_counter(),
                node_id=self.node_id,
                data={"message": message}
            ))
    
    async def _process_protocol(self) -> None:
        """处理协议逻辑."""
        # 检查超时
        if hasattr(self.protocol, 'check_timeouts'):
            self.protocol.check_timeouts()
    
    def send_message(self, message: Any) -> None:
        """发送消息到节点.
        
        Args:
            message: 要发送的消息
        """
        self.message_queue.put_nowait(message)
    
    def set_event_handler(self, handler: Callable[[SimulationEvent], None]) -> None:
        """设置事件处理器.
        
        Args:
            handler: 事件处理函数
        """
        self.event_handler = handler


class SimulationEngine:
    """并发仿真引擎.
    
    管理多个仿真节点的并发执行和协调。
    
    Attributes:
        config: 仿真配置
        nodes: 仿真节点字典
        event_log: 事件日志
        _running: 是否正在运行
    """
    
    def __init__(self, config: Optional[SimulationConfig] = None) -> None:
        """初始化仿真引擎.
        
        Args:
            config: 仿真配置
        """
        self.config = config or SimulationConfig()
        self.nodes: dict[int, SimulationNode] = {}
        self.event_log: list[SimulationEvent] = []
        self._running: bool = False
        self._start_time: float = 0
    
    def add_node(self, node: SimulationNode) -> None:
        """添加仿真节点.
        
        Args:
            node: 仿真节点
        """
        self.nodes[node.node_id] = node
        node.set_event_handler(self._on_node_event)
    
    def remove_node(self, node_id: int) -> None:
        """移除仿真节点.
        
        Args:
            node_id: 节点 ID
        """
        if node_id in self.nodes:
            del self.nodes[node_id]
    
    def _on_node_event(self, event: SimulationEvent) -> None:
        """处理节点事件.
        
        Args:
            event: 仿真事件
        """
        self.event_log.append(event)
        
        if self.config.enable_logging:
            print(f"[{event.timestamp:.6f}] Node {event.node_id}: {event.event_type.name}")
    
    async def run(self) -> None:
        """运行仿真."""
        self._running = True
        self._start_time = time.perf_counter()
        
        # 启动所有节点
        for node in self.nodes.values():
            await node.start()
        
        # 仿真主循环
        try:
            while self._running:
                elapsed_ms = (time.perf_counter() - self._start_time) * 1000
                
                # 检查仿真时间
                if elapsed_ms >= self.config.simulation_time_ms:
                    break
                
                # 检查事件数限制
                if len(self.event_log) >= self.config.max_events:
                    break
                
                # 短暂休眠
                await asyncio.sleep(0.001 * self.config.time_scale)
        
        finally:
            # 停止所有节点
            for node in self.nodes.values():
                await node.stop()
            
            self._running = False
    
    def stop(self) -> None:
        """停止仿真."""
        self._running = False
    
    def send_message_between_nodes(
        self,
        from_node: int,
        to_node: int,
        message: Any,
        delay_ms: float = 0
    ) -> None:
        """在节点间发送消息.
        
        Args:
            from_node: 源节点 ID
            to_node: 目标节点 ID
            message: 消息
            delay_ms: 延迟（毫秒）
        """
        if to_node not in self.nodes:
            raise SimulationError(f"目标节点 {to_node} 不存在")
        
        # 记录发送事件
        self.event_log.append(SimulationEvent(
            event_type=SimulationEventType.MESSAGE_SENT,
            timestamp=time.perf_counter(),
            node_id=from_node,
            data={"to_node": to_node, "message": message}
        ))
        
        # 发送消息
        self.nodes[to_node].send_message(message)
    
    def broadcast_message(
        self,
        from_node: int,
        message: Any,
        exclude_self: bool = True
    ) -> None:
        """广播消息到所有节点.
        
        Args:
            from_node: 源节点 ID
            message: 消息
            exclude_self: 是否排除自己
        """
        for node_id in self.nodes:
            if exclude_self and node_id == from_node:
                continue
            self.send_message_between_nodes(from_node, node_id, message)
    
    def get_event_log(self) -> list[SimulationEvent]:
        """获取事件日志.
        
        Returns:
            事件日志列表
        """
        return self.event_log.copy()
    
    def get_statistics(self) -> dict[str, Any]:
        """获取仿真统计信息.
        
        Returns:
            统计信息字典
        """
        event_counts = {}
        for event in self.event_log:
            event_type = event.event_type.name
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        return {
            "total_events": len(self.event_log),
            "event_counts": event_counts,
            "node_count": len(self.nodes),
            "simulation_duration_ms": (time.perf_counter() - self._start_time) * 1000,
        }
    
    def clear_event_log(self) -> None:
        """清空事件日志."""
        self.event_log.clear()


class ProtocolSimulationBuilder:
    """协议仿真构建器.
    
    简化协议仿真场景的构建。
    """
    
    def __init__(self) -> None:
        """初始化构建器."""
        self.engine = SimulationEngine()
        self._next_node_id = 1
    
    def add_protocol_node(self, protocol: Any, node_id: Optional[int] = None) -> int:
        """添加协议节点.
        
        Args:
            protocol: 协议实例
            node_id: 节点 ID（自动分配如果为 None）
            
        Returns:
            节点 ID
        """
        if node_id is None:
            node_id = self._next_node_id
            self._next_node_id += 1
        
        node = SimulationNode(node_id, protocol)
        self.engine.add_node(node)
        return node_id
    
    def connect_nodes(self, node1_id: int, node2_id: int) -> None:
        """连接两个节点（设置对端 ID）.
        
        Args:
            node1_id: 节点 1 ID
            node2_id: 节点 2 ID
        """
        if node1_id in self.engine.nodes:
            node1 = self.engine.nodes[node1_id]
            if hasattr(node1.protocol, 'peer_node_id'):
                node1.protocol.peer_node_id = node2_id
        
        if node2_id in self.engine.nodes:
            node2 = self.engine.nodes[node2_id]
            if hasattr(node2.protocol, 'peer_node_id'):
                node2.protocol.peer_node_id = node1_id
    
    def build(self) -> SimulationEngine:
        """构建仿真引擎.
        
        Returns:
            配置好的仿真引擎
        """
        return self.engine
    
    async def run_simulation(self, duration_ms: float = 5000) -> dict[str, Any]:
        """运行仿真并返回结果.
        
        Args:
            duration_ms: 仿真时长（毫秒）
            
        Returns:
            仿真结果统计
        """
        self.engine.config.simulation_time_ms = duration_ms
        await self.engine.run()
        return self.engine.get_statistics()
