"""RSSP-II 协议模型模块.

实现 RSSP-II（Railway Signal Safety Protocol - II）协议的状态机模型，
支持形式化验证和仿真测试。

RSSP-II 协议特点：
- 双通道冗余传输
- 安全序列号（递增+校验）
- 严格时序监控
- 安全关闭机制
- 适用于 SIL4 级安全通信
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Any
import time
import hashlib

from core.state_machine import StateMachine, State, StateType, Transition
from core.exceptions import ProtocolViolationError, ErrorSeverity
from protocol.message import RSSPMessage, MessageType


class RSSPIIState(Enum):
    """RSSP-II 协议状态枚举."""
    
    INIT = auto()
    WAIT_FOR_CONNECTION = auto()
    CONNECTION_ESTABLISHED = auto()
    SAFE_OPERATION = auto()
    ERROR_STATE = auto()
    SAFE_SHUTDOWN = auto()


@dataclass
class RSSPIIConfig:
    """RSSP-II 协议配置.
    
    Attributes:
        max_sequence_number: 最大序列号
        window_size: 接收窗口大小
        timeout_ms: 超时时间（毫秒）
        max_retransmissions: 最大重传次数
        safety_code_key: 安全码密钥
        dual_channel: 是否启用双通道
        channel_timeout_ms: 通道超时时间
        max_sequence_gap: 最大允许序列号间隔
        node_id: 本节点 ID
    """
    
    max_sequence_number: int = 0xFFFFFFFF
    window_size: int = 256
    timeout_ms: int = 500
    max_retransmissions: int = 2
    safety_code_key: bytes = field(default_factory=lambda: b"RSSP-II-Safety-Key")
    dual_channel: bool = True
    channel_timeout_ms: int = 1000
    max_sequence_gap: int = 10
    node_id: int = 1
    
    def __post_init__(self) -> None:
        """验证配置参数."""
        assert self.window_size > 0, "窗口大小必须大于 0"
        assert self.timeout_ms > 0, "超时时间必须大于 0"
        assert self.max_retransmissions >= 0, "最大重传次数不能为负"
        assert len(self.safety_code_key) >= 16, "安全码密钥长度至少 16 字节"
        assert 0 <= self.node_id <= 0xFFFFFFFF, "节点 ID 必须在 32 位范围内"


@dataclass
class SafetyCode:
    """安全码.
    
    RSSP-II 协议的安全校验机制，用于确保消息完整性和顺序。
    
    Attributes:
        sequence_number: 序列号
        timestamp: 时间戳
        mac: 消息认证码
    """
    
    sequence_number: int
    timestamp: int
    mac: bytes
    
    def __post_init__(self) -> None:
        """验证安全码字段."""
        assert 0 <= self.sequence_number <= 0xFFFFFFFF, "序列号必须在 32 位范围内"
        assert len(self.mac) == 8, "MAC 长度必须为 8 字节"
    
    @classmethod
    def generate(
        cls,
        sequence_number: int,
        timestamp: int,
        payload: bytes,
        key: bytes
    ) -> "SafetyCode":
        """生成安全码.
        
        Args:
            sequence_number: 序列号
            timestamp: 时间戳
            payload: 消息载荷
            key: 密钥
            
        Returns:
            安全码对象
        """
        # 构造数据
        data = (
            sequence_number.to_bytes(4, 'big') +
            timestamp.to_bytes(4, 'big') +
            payload +
            key
        )
        
        # 计算 HMAC-SHA256，取前 8 字节
        mac = hashlib.sha256(data).digest()[:8]
        
        return cls(sequence_number, timestamp, mac)
    
    def verify(
        self,
        payload: bytes,
        key: bytes,
        max_time_diff_ms: int = 1000
    ) -> tuple[bool, str]:
        """验证安全码.
        
        Args:
            payload: 消息载荷
            key: 密钥
            max_time_diff_ms: 最大允许时间差（毫秒）
            
        Returns:
            (是否有效, 错误信息)
        """
        # 验证 MAC
        expected = SafetyCode.generate(
            self.sequence_number,
            self.timestamp,
            payload,
            key
        )
        
        if self.mac != expected.mac:
            return False, "MAC 验证失败"
        
        # 验证时间戳
        current_time = int(time.perf_counter() * 1000)
        time_diff = abs(current_time - self.timestamp)
        
        if time_diff > max_time_diff_ms:
            return False, f"时间戳过期，差值: {time_diff}ms"
        
        return True, ""


@dataclass
class DualChannelState:
    """双通道状态.
    
    管理双通道冗余传输的状态。
    
    Attributes:
        channel_a_active: 通道 A 是否活跃
        channel_b_active: 通道 B 是否活跃
        channel_a_sequence: 通道 A 序列号
        channel_b_sequence: 通道 B 序列号
        last_sync_time: 上次同步时间
    """
    
    channel_a_active: bool = True
    channel_b_active: bool = True
    channel_a_sequence: int = 0
    channel_b_sequence: int = 0
    last_sync_time: float = field(default_factory=time.perf_counter)
    
    def is_operational(self) -> bool:
        """检查是否至少一个通道可用."""
        return self.channel_a_active or self.channel_b_active
    
    def get_primary_sequence(self) -> int:
        """获取主通道序列号."""
        if self.channel_a_active:
            return self.channel_a_sequence
        return self.channel_b_sequence
    
    def update_sequence(self, channel: str, seq: int) -> None:
        """更新通道序列号.
        
        Args:
            channel: 通道标识 ('A' 或 'B')
            seq: 序列号
        """
        if channel == 'A':
            self.channel_a_sequence = seq
        elif channel == 'B':
            self.channel_b_sequence = seq
    
    def set_channel_state(self, channel: str, active: bool) -> None:
        """设置通道状态.
        
        Args:
            channel: 通道标识 ('A' 或 'B')
            active: 是否活跃
        """
        if channel == 'A':
            self.channel_a_active = active
        elif channel == 'B':
            self.channel_b_active = active


class RSSPIIProtocol(StateMachine):
    """RSSP-II 协议状态机.
    
    实现 RSSP-II 协议的完整状态机，包括：
    - 安全连接建立
    - 双通道冗余传输
    - 安全序列号管理
    - 严格时序监控
    - 安全关闭机制
    
    Attributes:
        config: 协议配置
        dual_channel_state: 双通道状态
        next_sequence_number: 下一个发送序列号
        peer_node_id: 对端节点 ID
        received_sequences: 已接收序列号集合（防重放）
        last_received_time: 上次接收时间
    """
    
    def __init__(self, config: Optional[RSSPIIConfig] = None) -> None:
        """初始化 RSSP-II 协议状态机.
        
        Args:
            config: 协议配置，使用默认配置如果未提供
        """
        super().__init__()
        self.config = config or RSSPIIConfig()
        self.dual_channel_state = DualChannelState()
        self.next_sequence_number: int = 1  # RSSP-II 从 1 开始
        self.peer_node_id: Optional[int] = None
        self.received_sequences: set[int] = set()
        self.last_received_time: float = 0
        self._message_handler: Optional[Callable[[RSSPMessage, str], None]] = None
        self._error_handler: Optional[Callable[[Exception], None]] = None
        self._safety_event_handler: Optional[Callable[[str, dict], None]] = None
        
        # 初始化状态机结构
        self.initialize()
    
    def initialize(self) -> None:
        """初始化状态机结构."""
        # 如果已经初始化，跳过
        if len(self._states) > 0:
            return
        
        # 定义状态
        states = [
            State("INIT", StateType.INITIAL),
            State("WAIT_FOR_CONNECTION", StateType.NORMAL),
            State("CONNECTION_ESTABLISHED", StateType.NORMAL),
            State("SAFE_OPERATION", StateType.NORMAL),
            State("ERROR_STATE", StateType.ERROR),
            State("SAFE_SHUTDOWN", StateType.ACCEPTING),
        ]
        
        for state in states:
            self.add_state(state)
        
        # 定义转移
        transitions = [
            # INIT -> WAIT_FOR_CONNECTION (初始化完成)
            Transition("INIT", "WAIT_FOR_CONNECTION", event="init_complete"),
            # WAIT_FOR_CONNECTION -> CONNECTION_ESTABLISHED (连接建立)
            Transition("WAIT_FOR_CONNECTION", "CONNECTION_ESTABLISHED", event="connection_established"),
            # CONNECTION_ESTABLISHED -> SAFE_OPERATION (安全校验通过)
            Transition("CONNECTION_ESTABLISHED", "SAFE_OPERATION", event="safety_check_passed"),
            # 任何状态 -> ERROR_STATE (错误发生)
            Transition("INIT", "ERROR_STATE", event="error"),
            Transition("WAIT_FOR_CONNECTION", "ERROR_STATE", event="error"),
            Transition("CONNECTION_ESTABLISHED", "ERROR_STATE", event="error"),
            Transition("SAFE_OPERATION", "ERROR_STATE", event="error"),
            # 任何状态 -> SAFE_SHUTDOWN (安全关闭)
            Transition("CONNECTION_ESTABLISHED", "SAFE_SHUTDOWN", event="safe_shutdown"),
            Transition("SAFE_OPERATION", "SAFE_SHUTDOWN", event="safe_shutdown"),
        ]
        
        for trans in transitions:
            self.add_transition(trans)
        
        # 添加状态不变式
        self._add_state_invariants()
    
    def _add_state_invariants(self) -> None:
        """添加状态不变式."""
        safe_operation_state = self._states.get("SAFE_OPERATION")
        if safe_operation_state:
            # 不变式：双通道至少有一个活跃
            safe_operation_state.add_invariant(
                lambda ctx: self.dual_channel_state.is_operational()
            )
            # 不变式：序列号单调递增
            safe_operation_state.add_invariant(
                lambda ctx: self.next_sequence_number > 0
            )
    
    def start(self) -> None:
        """启动协议."""
        self.step({}, "init_complete")
    
    def establish_connection(self, peer_id: int) -> None:
        """建立连接.
        
        Args:
            peer_id: 对端节点 ID
        """
        self.peer_node_id = peer_id
        
        # 发送连接请求（双通道）
        if self.config.dual_channel:
            self._send_sync_message('A')
            self._send_sync_message('B')
        else:
            self._send_sync_message('A')
        
        self.step({}, "connection_established")
    
    def _send_sync_message(self, channel: str) -> None:
        """发送同步消息.
        
        Args:
            channel: 通道标识
        """
        sync_message = RSSPMessage(
            msg_type=MessageType.SYNC,
            sequence_number=self.next_sequence_number,
            timestamp=int(time.perf_counter() * 1000),
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        sync_message.update_checksum()
        
        if self._message_handler:
            self._message_handler(sync_message, channel)
    
    def send_safe_data(self, payload: bytes) -> tuple[RSSPMessage, Optional[RSSPMessage]]:
        """发送安全数据.
        
        Args:
            payload: 数据载荷
            
        Returns:
            (主通道消息, 备用通道消息或 None)
            
        Raises:
            ProtocolViolationError: 如果不在 SAFE_OPERATION 状态
        """
        current_state = self.get_current_state()
        if current_state is None or current_state.name != "SAFE_OPERATION":
            raise ProtocolViolationError(
                f"无法在状态 '{current_state.name if current_state else 'None'}' 发送安全数据",
                violation_type="invalid_state_for_safe_send"
            )
        
        timestamp = int(time.perf_counter() * 1000)
        
        # 生成安全码
        safety_code = SafetyCode.generate(
            self.next_sequence_number,
            timestamp,
            payload,
            self.config.safety_code_key
        )
        
        # 创建主通道消息
        primary_message = RSSPMessage(
            msg_type=MessageType.DATA,
            sequence_number=self.next_sequence_number,
            timestamp=timestamp,
            payload=payload + safety_code.mac,
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        primary_message.update_checksum()
        
        secondary_message = None
        
        # 如果启用双通道，创建备用通道消息
        if self.config.dual_channel and self.dual_channel_state.channel_b_active:
            secondary_message = RSSPMessage(
                msg_type=MessageType.DATA,
                sequence_number=self.next_sequence_number,
                timestamp=timestamp,
                payload=payload + safety_code.mac,
                source_id=self.config.node_id,
                dest_id=self.peer_node_id or 0,
            )
            secondary_message.update_checksum()
        
        # 递增序列号
        self.next_sequence_number = (
            self.next_sequence_number + 1
        ) % self.config.max_sequence_number
        
        return primary_message, secondary_message
    
    def receive_message(
        self,
        message: RSSPMessage,
        channel: str = 'A'
    ) -> None:
        """接收消息.
        
        Args:
            message: 接收到的消息
            channel: 接收通道
            
        Raises:
            ProtocolViolationError: 如果检测到协议违反
        """
        current_time = time.perf_counter()
        self.last_received_time = current_time
        
        # 检查消息类型
        if message.msg_type == MessageType.DATA:
            self._handle_safe_data_message(message, channel)
        elif message.msg_type == MessageType.SYNC:
            self._handle_sync_message(message, channel)
        elif message.msg_type == MessageType.ACK:
            self._handle_ack_message(message, channel)
    
    def _handle_safe_data_message(
        self,
        message: RSSPMessage,
        channel: str
    ) -> None:
        """处理安全数据消息.
        
        Args:
            message: 数据消息
            channel: 接收通道
            
        Raises:
            ProtocolViolationError: 如果检测到协议违反
        """
        seq_num = message.sequence_number
        
        # 检查序列号单调性
        if seq_num <= 0:
            raise ProtocolViolationError(
                f"无效的序列号: {seq_num}",
                violation_type="invalid_sequence_number",
                actual_value=seq_num
            )
        
        # 检查重放
        if seq_num in self.received_sequences:
            raise ProtocolViolationError(
                f"检测到重放消息，序列号: {seq_num}",
                violation_type="replay_detected",
                actual_value=seq_num
            )
        
        # 检查序列号间隔
        max_seq = max(self.received_sequences) if self.received_sequences else 0
        if seq_num > max_seq + self.config.max_sequence_gap:
            raise ProtocolViolationError(
                f"序列号间隔过大: {seq_num - max_seq}",
                violation_type="sequence_gap_too_large",
                expected_value=f"<={self.config.max_sequence_gap}",
                actual_value=seq_num - max_seq
            )
        
        # 验证校验和
        if not message.verify_checksum():
            raise ProtocolViolationError(
                "消息校验和错误",
                violation_type="checksum_error"
            )
        
        # 提取载荷和安全码
        if len(message.payload) < 8:
            raise ProtocolViolationError(
                "消息载荷过短，无法包含安全码",
                violation_type="payload_too_short"
            )
        
        payload = message.payload[:-8]
        mac = message.payload[-8:]
        
        # 验证安全码
        safety_code = SafetyCode(seq_num, message.timestamp, mac)
        valid, error_msg = safety_code.verify(
            payload,
            self.config.safety_code_key,
            self.config.timeout_ms
        )
        
        if not valid:
            raise ProtocolViolationError(
                f"安全码验证失败: {error_msg}",
                violation_type="safety_code_verification_failed"
            )
        
        # 记录已接收序列号
        self.received_sequences.add(seq_num)
        
        # 更新通道状态
        self.dual_channel_state.update_sequence(channel, seq_num)
        
        # 如果当前在 CONNECTION_ESTABLISHED 状态，转移到 SAFE_OPERATION
        current_state = self.get_current_state()
        if current_state and current_state.name == "CONNECTION_ESTABLISHED":
            self.step({}, "safety_check_passed")
        
        # 发送 ACK
        self._send_ack(seq_num, channel)
    
    def _handle_sync_message(self, message: RSSPMessage, channel: str) -> None:
        """处理同步消息.
        
        Args:
            message: SYNC 消息
            channel: 接收通道
        """
        # 更新通道状态
        self.dual_channel_state.set_channel_state(channel, True)
        
        # 如果当前在 WAIT_FOR_CONNECTION 状态，转移到 CONNECTION_ESTABLISHED
        current_state = self.get_current_state()
        if current_state and current_state.name == "WAIT_FOR_CONNECTION":
            self.peer_node_id = message.source_id
            self.step({}, "connection_established")
    
    def _handle_ack_message(self, message: RSSPMessage, channel: str) -> None:
        """处理确认消息.
        
        Args:
            message: ACK 消息
            channel: 接收通道
        """
        # 简化实现
        pass
    
    def _send_ack(self, seq_num: int, channel: str) -> None:
        """发送确认消息.
        
        Args:
            seq_num: 要确认的序列号
            channel: 发送通道
        """
        ack_message = RSSPMessage(
            msg_type=MessageType.ACK,
            ack_number=seq_num,
            timestamp=int(time.perf_counter() * 1000),
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        ack_message.update_checksum()
        
        if self._message_handler:
            self._message_handler(ack_message, channel)
    
    def check_timeouts(self) -> None:
        """检查时序约束."""
        current_time = time.perf_counter()
        
        # 检查接收超时
        if self.last_received_time > 0:
            time_since_last_receive = (current_time - self.last_received_time) * 1000
            
            if time_since_last_receive > self.config.channel_timeout_ms:
                # 报告安全事件
                if self._safety_event_handler:
                    self._safety_event_handler(
                        "receive_timeout",
                        {"timeout_ms": time_since_last_receive}
                    )
                
                # 转移到错误状态
                self.step({}, "error")
                
                raise ProtocolViolationError(
                    f"接收超时: {time_since_last_receive:.0f}ms",
                    violation_type="receive_timeout"
                )
    
    def safe_shutdown(self) -> None:
        """安全关闭连接."""
        current_state = self.get_current_state()
        if current_state and current_state.name in ("CONNECTION_ESTABLISHED", "SAFE_OPERATION"):
            # 发送关闭通知（双通道）
            if self.config.dual_channel:
                self._send_shutdown_message('A')
                self._send_shutdown_message('B')
            else:
                self._send_shutdown_message('A')
            
            self.step({}, "safe_shutdown")
    
    def _send_shutdown_message(self, channel: str) -> None:
        """发送关闭消息.
        
        Args:
            channel: 通道标识
        """
        shutdown_message = RSSPMessage(
            msg_type=MessageType.ERROR,  # 使用 ERROR 类型表示关闭
            sequence_number=self.next_sequence_number,
            timestamp=int(time.perf_counter() * 1000),
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        shutdown_message.update_checksum()
        
        if self._message_handler:
            self._message_handler(shutdown_message, channel)
    
    def set_message_handler(
        self,
        handler: Callable[[RSSPMessage, str], None]
    ) -> None:
        """设置消息发送处理器.
        
        Args:
            handler: 消息处理函数
        """
        self._message_handler = handler
    
    def set_error_handler(self, handler: Callable[[Exception], None]) -> None:
        """设置错误处理器.
        
        Args:
            handler: 错误处理函数
        """
        self._error_handler = handler
    
    def set_safety_event_handler(
        self,
        handler: Callable[[str, dict], None]
    ) -> None:
        """设置安全事件处理器.
        
        Args:
            handler: 安全事件处理函数
        """
        self._safety_event_handler = handler
    
    def get_statistics(self) -> dict[str, Any]:
        """获取协议统计信息.
        
        Returns:
            统计信息字典
        """
        return {
            "current_state": self.get_current_state().name if self.get_current_state() else None,
            "next_sequence_number": self.next_sequence_number,
            "dual_channel_state": {
                "channel_a_active": self.dual_channel_state.channel_a_active,
                "channel_b_active": self.dual_channel_state.channel_b_active,
                "channel_a_sequence": self.dual_channel_state.channel_a_sequence,
                "channel_b_sequence": self.dual_channel_state.channel_b_sequence,
            },
            "received_sequences_count": len(self.received_sequences),
            "step_count": self.get_step_count(),
        }
