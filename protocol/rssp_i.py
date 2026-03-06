"""RSSP-I 协议模型模块.

实现 RSSP-I（Railway Signal Safety Protocol - I）协议的状态机模型，
支持形式化验证和仿真测试。

RSSP-I 协议特点：
- 基于序列号的顺序传输
- 超时重传机制
- 接收窗口管理
- 数据完整性校验
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Any
import time

from core.state_machine import StateMachine, State, StateType, Transition
from core.exceptions import ProtocolViolationError, ErrorSeverity
from protocol.message import RSSPMessage, MessageType


class RSSPIState(Enum):
    """RSSP-I 协议状态枚举."""
    
    CLOSED = auto()
    LISTEN = auto()
    SYN_SENT = auto()
    SYN_RECEIVED = auto()
    ESTABLISHED = auto()
    FIN_WAIT = auto()
    CLOSING = auto()
    TIME_WAIT = auto()


@dataclass
class RSSPIConfig:
    """RSSP-I 协议配置.
    
    Attributes:
        max_sequence_number: 最大序列号（默认 2^32 - 1）
        window_size: 接收窗口大小
        timeout_ms: 超时时间（毫秒）
        max_retransmissions: 最大重传次数
        heartbeat_interval_ms: 心跳间隔（毫秒）
        node_id: 本节点 ID
    """
    
    max_sequence_number: int = 0xFFFFFFFF
    window_size: int = 1024
    timeout_ms: int = 1000
    max_retransmissions: int = 3
    heartbeat_interval_ms: int = 5000
    node_id: int = 1
    
    def __post_init__(self) -> None:
        """验证配置参数."""
        assert self.window_size > 0, "窗口大小必须大于 0"
        assert self.timeout_ms > 0, "超时时间必须大于 0"
        assert self.max_retransmissions >= 0, "最大重传次数不能为负"
        assert 0 <= self.node_id <= 0xFFFFFFFF, "节点 ID 必须在 32 位范围内"


@dataclass
class SendBuffer:
    """发送缓冲区.
    
    管理已发送但未确认的消息。
    
    Attributes:
        messages: 消息字典（序列号 -> 消息）
        send_times: 发送时间字典
        retransmission_count: 重传次数字典
    """
    
    messages: dict[int, RSSPMessage] = field(default_factory=dict)
    send_times: dict[int, float] = field(default_factory=dict)
    retransmission_count: dict[int, int] = field(default_factory=dict)
    
    def add(self, seq_num: int, message: RSSPMessage) -> None:
        """添加消息到缓冲区.
        
        Args:
            seq_num: 序列号
            message: 消息对象
        """
        self.messages[seq_num] = message
        self.send_times[seq_num] = time.perf_counter()
        self.retransmission_count[seq_num] = 0
    
    def remove(self, seq_num: int) -> None:
        """从缓冲区移除消息.
        
        Args:
            seq_num: 序列号
        """
        self.messages.pop(seq_num, None)
        self.send_times.pop(seq_num, None)
        self.retransmission_count.pop(seq_num, None)
    
    def get_unacknowledged(self, timeout_ms: float) -> list[int]:
        """获取超时未确认的消息.
        
        Args:
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            超时消息的序列号列表
        """
        current_time = time.perf_counter()
        timeout_sec = timeout_ms / 1000.0
        
        return [
            seq for seq, send_time in self.send_times.items()
            if (current_time - send_time) > timeout_sec
        ]
    
    def increment_retransmission(self, seq_num: int) -> int:
        """增加重传计数.
        
        Args:
            seq_num: 序列号
            
        Returns:
            当前重传次数
        """
        if seq_num in self.retransmission_count:
            self.retransmission_count[seq_num] += 1
            return self.retransmission_count[seq_num]
        return 0
    
    def clear(self) -> None:
        """清空缓冲区."""
        self.messages.clear()
        self.send_times.clear()
        self.retransmission_count.clear()


@dataclass
class ReceiveWindow:
    """接收窗口.
    
    管理期望接收的消息序列号范围。
    
    Attributes:
        base: 窗口基线（期望的下一个序列号）
        size: 窗口大小
        received: 已接收的序列号集合
    """
    
    base: int = 0
    size: int = 1024
    received: set[int] = field(default_factory=set)
    
    def is_within_window(self, seq_num: int) -> bool:
        """检查序列号是否在窗口内.
        
        Args:
            seq_num: 序列号
            
        Returns:
            是否在窗口内
        """
        if seq_num < self.base:
            return False
        return seq_num < self.base + self.size
    
    def is_expected(self, seq_num: int) -> bool:
        """检查是否为期望的序列号.
        
        Args:
            seq_num: 序列号
            
        Returns:
            是否为期望序列号
        """
        return seq_num == self.base
    
    def advance(self) -> None:
        """推进窗口基线."""
        self.base += 1
        # 清理已不在窗口内的记录
        self.received = {s for s in self.received if s >= self.base}
    
    def record_received(self, seq_num: int) -> None:
        """记录已接收的序列号.
        
        Args:
            seq_num: 序列号
        """
        self.received.add(seq_num)
    
    def has_received(self, seq_num: int) -> bool:
        """检查序列号是否已接收.
        
        Args:
            seq_num: 序列号
            
        Returns:
            是否已接收
        """
        return seq_num in self.received


class RSSPIProtocol(StateMachine):
    """RSSP-I 协议状态机.
    
    实现 RSSP-I 协议的完整状态机，包括：
    - 连接建立（三次握手）
    - 数据传输（带序列号）
    - 超时重传
    - 接收窗口管理
    - 连接关闭
    
    Attributes:
        config: 协议配置
        send_buffer: 发送缓冲区
        receive_window: 接收窗口
        next_sequence_number: 下一个发送序列号
        peer_node_id: 对端节点 ID
        state_handlers: 状态处理函数字典
    """
    
    def __init__(self, config: Optional[RSSPIConfig] = None) -> None:
        """初始化 RSSP-I 协议状态机.
        
        Args:
            config: 协议配置，使用默认配置如果未提供
        """
        super().__init__()
        self.config = config or RSSPIConfig()
        self.send_buffer = SendBuffer()
        self.receive_window = ReceiveWindow(size=self.config.window_size)
        self.next_sequence_number: int = 0
        self.peer_node_id: Optional[int] = None
        self.state_handlers: dict[str, Callable[[RSSPMessage], None]] = {}
        self._message_handler: Optional[Callable[[RSSPMessage], None]] = None
        self._error_handler: Optional[Callable[[Exception], None]] = None
        
        # 初始化状态机结构
        self.initialize()
    
    def initialize(self) -> None:
        """初始化状态机结构."""
        # 如果已经初始化，跳过
        if len(self._states) > 0:
            return
        
        # 定义状态
        states = [
            State("CLOSED", StateType.INITIAL),
            State("LISTEN", StateType.NORMAL),
            State("SYN_SENT", StateType.NORMAL),
            State("SYN_RECEIVED", StateType.NORMAL),
            State("ESTABLISHED", StateType.NORMAL),
            State("FIN_WAIT", StateType.NORMAL),
            State("CLOSING", StateType.NORMAL),
            State("TIME_WAIT", StateType.NORMAL),
        ]
        
        for state in states:
            self.add_state(state)
        
        # 定义转移
        transitions = [
            # CLOSED -> SYN_SENT (主动打开)
            Transition("CLOSED", "SYN_SENT", event="active_open"),
            # CLOSED -> LISTEN (被动打开)
            Transition("CLOSED", "LISTEN", event="passive_open"),
            # LISTEN -> SYN_RECEIVED (收到 SYN)
            Transition("LISTEN", "SYN_RECEIVED", event="recv_syn"),
            # SYN_SENT -> SYN_RECEIVED (收到 SYN)
            Transition("SYN_SENT", "SYN_RECEIVED", event="recv_syn"),
            # SYN_SENT -> ESTABLISHED (收到 SYN-ACK)
            Transition("SYN_SENT", "ESTABLISHED", event="recv_synack"),
            # SYN_RECEIVED -> ESTABLISHED (收到 ACK)
            Transition("SYN_RECEIVED", "ESTABLISHED", event="recv_ack"),
            # ESTABLISHED -> FIN_WAIT (主动关闭)
            Transition("ESTABLISHED", "FIN_WAIT", event="active_close"),
            # FIN_WAIT -> CLOSING (收到 FIN)
            Transition("FIN_WAIT", "CLOSING", event="recv_fin"),
            # CLOSING -> TIME_WAIT (收到 ACK)
            Transition("CLOSING", "TIME_WAIT", event="recv_ack"),
            # TIME_WAIT -> CLOSED (超时)
            Transition("TIME_WAIT", "CLOSED", event="timeout"),
        ]
        
        for trans in transitions:
            self.add_transition(trans)
        
        # 注册状态处理函数
        self._register_state_handlers()
    
    def _register_state_handlers(self) -> None:
        """注册状态处理函数."""
        self.state_handlers = {
            "CLOSED": self._handle_closed,
            "LISTEN": self._handle_listen,
            "SYN_SENT": self._handle_syn_sent,
            "SYN_RECEIVED": self._handle_syn_received,
            "ESTABLISHED": self._handle_established,
            "FIN_WAIT": self._handle_fin_wait,
            "CLOSING": self._handle_closing,
            "TIME_WAIT": self._handle_time_wait,
        }
    
    def _handle_closed(self, message: RSSPMessage) -> None:
        """处理 CLOSED 状态消息."""
        # 在 CLOSED 状态，只接受 SYNC 消息
        if message.msg_type == MessageType.SYNC:
            # 转移到 LISTEN 状态
            self.step({}, "passive_open")
    
    def _handle_listen(self, message: RSSPMessage) -> None:
        """处理 LISTEN 状态消息."""
        if message.msg_type == MessageType.SYNC:
            # 收到 SYN，转移到 SYN_RECEIVED
            self.peer_node_id = message.source_id
            self.step({}, "recv_syn")
    
    def _handle_syn_sent(self, message: RSSPMessage) -> None:
        """处理 SYN_SENT 状态消息."""
        if message.msg_type == MessageType.SYNC:
            # 收到 SYN，转移到 SYN_RECEIVED
            self.step({}, "recv_syn")
        elif message.msg_type == MessageType.ACK:
            # 收到 ACK，转移到 ESTABLISHED
            self.step({}, "recv_synack")
    
    def _handle_syn_received(self, message: RSSPMessage) -> None:
        """处理 SYN_RECEIVED 状态消息."""
        if message.msg_type == MessageType.ACK:
            # 收到 ACK，转移到 ESTABLISHED
            self.step({}, "recv_ack")
    
    def _handle_established(self, message: RSSPMessage) -> None:
        """处理 ESTABLISHED 状态消息."""
        if message.msg_type == MessageType.DATA:
            self._handle_data_message(message)
        elif message.msg_type == MessageType.ACK:
            self._handle_ack_message(message)
    
    def _handle_fin_wait(self, message: RSSPMessage) -> None:
        """处理 FIN_WAIT 状态消息."""
        pass  # 简化实现
    
    def _handle_closing(self, message: RSSPMessage) -> None:
        """处理 CLOSING 状态消息."""
        pass  # 简化实现
    
    def _handle_time_wait(self, message: RSSPMessage) -> None:
        """处理 TIME_WAIT 状态消息."""
        pass  # 简化实现
    
    def _handle_data_message(self, message: RSSPMessage) -> None:
        """处理数据消息.
        
        Args:
            message: 数据消息
            
        Raises:
            ProtocolViolationError: 如果检测到协议违反
        """
        seq_num = message.sequence_number
        
        # 检查序列号是否在接收窗口内
        if not self.receive_window.is_within_window(seq_num):
            raise ProtocolViolationError(
                f"序列号 {seq_num} 超出接收窗口范围",
                violation_type="sequence_out_of_window",
                expected_value=f"[{self.receive_window.base}, "
                              f"{self.receive_window.base + self.receive_window.size})",
                actual_value=seq_num
            )
        
        # 检查是否为重放消息
        if self.receive_window.has_received(seq_num):
            raise ProtocolViolationError(
                f"检测到重放消息，序列号: {seq_num}",
                violation_type="replay_detected",
                actual_value=seq_num
            )
        
        # 检查校验和
        if not message.verify_checksum():
            raise ProtocolViolationError(
                "消息校验和错误",
                violation_type="checksum_error",
                expected_value="valid",
                actual_value="invalid"
            )
        
        # 如果是期望的序列号，推进窗口
        if self.receive_window.is_expected(seq_num):
            self.receive_window.advance()
        else:
            # 记录已接收（乱序）
            self.receive_window.record_received(seq_num)
        
        # 发送 ACK
        self._send_ack(seq_num)
    
    def _handle_ack_message(self, message: RSSPMessage) -> None:
        """处理确认消息.
        
        Args:
            message: ACK 消息
        """
        ack_num = message.ack_number
        
        # 从发送缓冲区移除已确认的消息
        if ack_num in self.send_buffer.messages:
            self.send_buffer.remove(ack_num)
    
    def _send_ack(self, seq_num: int) -> None:
        """发送确认消息.
        
        Args:
            seq_num: 要确认的序列号
        """
        ack_message = RSSPMessage(
            msg_type=MessageType.ACK,
            ack_number=seq_num,
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        ack_message.update_checksum()
        
        if self._message_handler:
            self._message_handler(ack_message)
    
    def send_data(self, payload: bytes) -> RSSPMessage:
        """发送数据.
        
        Args:
            payload: 数据载荷
            
        Returns:
            发送的消息
            
        Raises:
            ProtocolViolationError: 如果不在 ESTABLISHED 状态
        """
        current_state = self.get_current_state()
        if current_state is None or current_state.name != "ESTABLISHED":
            raise ProtocolViolationError(
                f"无法在状态 '{current_state.name if current_state else 'None'}' 发送数据",
                violation_type="invalid_state_for_send"
            )
        
        # 创建消息
        message = RSSPMessage(
            msg_type=MessageType.DATA,
            sequence_number=self.next_sequence_number,
            timestamp=int(time.perf_counter() * 1000),
            payload=payload,
            source_id=self.config.node_id,
            dest_id=self.peer_node_id or 0,
        )
        message.update_checksum()
        
        # 添加到发送缓冲区
        self.send_buffer.add(self.next_sequence_number, message)
        
        # 递增序列号
        self.next_sequence_number = (self.next_sequence_number + 1) % self.config.max_sequence_number
        
        return message
    
    def receive_message(self, message: RSSPMessage) -> None:
        """接收消息.
        
        Args:
            message: 接收到的消息
            
        Raises:
            ProtocolViolationError: 如果检测到协议违反
        """
        current_state = self.get_current_state()
        if current_state is None:
            raise ProtocolViolationError("当前状态未设置")
        
        handler = self.state_handlers.get(current_state.name)
        if handler:
            try:
                handler(message)
            except Exception as e:
                if self._error_handler:
                    self._error_handler(e)
                raise
    
    def check_timeouts(self) -> list[RSSPMessage]:
        """检查超时并重传.
        
        Returns:
            需要重传的消息列表
        """
        timeout_messages = []
        
        for seq_num in self.send_buffer.get_unacknowledged(self.config.timeout_ms):
            # 检查重传次数
            retry_count = self.send_buffer.increment_retransmission(seq_num)
            
            if retry_count > self.config.max_retransmissions:
                # 超过最大重传次数，报告错误
                if self._error_handler:
                    self._error_handler(
                        ProtocolViolationError(
                            f"消息 {seq_num} 超过最大重传次数",
                            violation_type="max_retransmission_exceeded"
                        )
                    )
                self.send_buffer.remove(seq_num)
            else:
                # 重传消息
                message = self.send_buffer.messages.get(seq_num)
                if message:
                    timeout_messages.append(message)
        
        return timeout_messages
    
    def connect(self, peer_id: int) -> None:
        """主动建立连接.
        
        Args:
            peer_id: 对端节点 ID
        """
        self.peer_node_id = peer_id
        self.step({}, "active_open")
        
        # 发送 SYN 消息
        syn_message = RSSPMessage(
            msg_type=MessageType.SYNC,
            sequence_number=self.next_sequence_number,
            source_id=self.config.node_id,
            dest_id=peer_id,
        )
        syn_message.update_checksum()
        
        if self._message_handler:
            self._message_handler(syn_message)
    
    def close(self) -> None:
        """关闭连接."""
        current_state = self.get_current_state()
        if current_state and current_state.name == "ESTABLISHED":
            self.step({}, "active_close")
    
    def set_message_handler(self, handler: Callable[[RSSPMessage], None]) -> None:
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
    
    def get_statistics(self) -> dict[str, Any]:
        """获取协议统计信息.
        
        Returns:
            统计信息字典
        """
        return {
            "current_state": self.get_current_state().name if self.get_current_state() else None,
            "next_sequence_number": self.next_sequence_number,
            "receive_window_base": self.receive_window.base,
            "send_buffer_size": len(self.send_buffer.messages),
            "step_count": self.get_step_count(),
        }
