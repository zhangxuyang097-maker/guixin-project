"""RSSP 协议消息定义模块.

定义 RSSP-I/II 协议使用的消息格式和类型。
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any
import struct
import hashlib


class MessageType(Enum):
    """消息类型枚举."""
    
    DATA = auto()
    ACK = auto()
    NACK = auto()
    SYNC = auto()
    HEARTBEAT = auto()
    ERROR = auto()


@dataclass
class RSSPMessage:
    """RSSP 消息数据类.
    
    表示 RSSP-I/II 协议中的消息格式。
    
    Attributes:
        msg_type: 消息类型
        sequence_number: 序列号
        ack_number: 确认号
        timestamp: 时间戳
        payload: 消息载荷
        checksum: 校验和
        source_id: 源节点 ID
        dest_id: 目标节点 ID
    """
    
    msg_type: MessageType
    sequence_number: int = 0
    ack_number: int = 0
    timestamp: int = 0
    payload: bytes = field(default_factory=bytes)
    checksum: int = 0
    source_id: int = 0
    dest_id: int = 0
    
    def __post_init__(self) -> None:
        """验证消息字段."""
        assert isinstance(self.msg_type, MessageType), "消息类型必须是 MessageType 枚举"
        assert 0 <= self.sequence_number <= 0xFFFFFFFF, "序列号必须在 32 位范围内"
        assert 0 <= self.ack_number <= 0xFFFFFFFF, "确认号必须在 32 位范围内"
        assert len(self.payload) <= 65535, "载荷长度不能超过 65535 字节"
    
    def calculate_checksum(self) -> int:
        """计算消息校验和.
        
        使用 CRC32 算法计算校验和。
        
        Returns:
            32 位校验和
        """
        # 序列化消息内容（不含校验和字段）
        data = self._serialize_without_checksum()
        
        # 计算 CRC32
        crc = 0xFFFFFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
        
        return (~crc) & 0xFFFFFFFF
    
    def verify_checksum(self) -> bool:
        """验证消息校验和.
        
        Returns:
            校验和是否正确
        """
        return self.checksum == self.calculate_checksum()
    
    def _serialize_without_checksum(self) -> bytes:
        """序列化消息（不含校验和）.
        
        Returns:
            序列化字节流
        """
        # 头部: msg_type(1) + reserved(1) + seq(4) + ack(4) + ts(4) + src(4) + dst(4) = 22 字节
        header = struct.pack(
            "!BBIIIII",
            self.msg_type.value,
            0,  # 保留字段
            self.sequence_number,
            self.ack_number,
            self.timestamp,
            self.source_id,
            self.dest_id,
        )
        # payload 长度: 2 字节
        length = struct.pack("!H", len(self.payload))
        return header + length + self.payload
    
    def serialize(self) -> bytes:
        """序列化消息.
        
        Returns:
            序列化字节流
        """
        data = self._serialize_without_checksum()
        checksum = struct.pack("!I", self.checksum)
        return data + checksum
    
    @classmethod
    def deserialize(cls, data: bytes) -> "RSSPMessage":
        """反序列化消息.
        
        Args:
            data: 序列化字节流
            
        Returns:
            反序列化的消息对象
            
        Raises:
            ValueError: 如果数据格式无效
        """
        # 最小消息大小: header(22) + length(2) + checksum(4) = 28 bytes (空 payload)
        if len(data) < 28:
            raise ValueError(f"数据长度不足，需要至少 28 字节，实际 {len(data)} 字节")
        
        try:
            # 解析头部 (22 字节)
            msg_type_val, _, seq, ack, ts, src, dst = struct.unpack("!BBIIIII", data[:22])
            # 解析 payload 长度 (2 字节)
            payload_len = struct.unpack("!H", data[22:24])[0]
            
            # 验证数据长度是否足够
            expected_len = 24 + payload_len + 4  # header + length + payload + checksum
            if len(data) < expected_len:
                raise ValueError(f"数据长度不足，期望 {expected_len} 字节，实际 {len(data)} 字节")
            
            # 解析 payload
            payload = data[24:24 + payload_len]
            # 解析 checksum (4 字节)
            checksum = struct.unpack("!I", data[24 + payload_len:28 + payload_len])[0]
            
            return cls(
                msg_type=MessageType(msg_type_val),
                sequence_number=seq,
                ack_number=ack,
                timestamp=ts,
                payload=payload,
                checksum=checksum,
                source_id=src,
                dest_id=dst,
            )
        except struct.error as e:
            raise ValueError(f"反序列化失败: {e}")
    
    def update_checksum(self) -> None:
        """更新消息校验和."""
        self.checksum = self.calculate_checksum()
    
    def is_data_message(self) -> bool:
        """检查是否为数据消息."""
        return self.msg_type == MessageType.DATA
    
    def is_control_message(self) -> bool:
        """检查是否为控制消息."""
        return self.msg_type in (MessageType.ACK, MessageType.NACK, MessageType.SYNC)
    
    def get_size(self) -> int:
        """获取消息大小.
        
        Returns:
            消息字节数
        """
        return 26 + len(self.payload)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式."""
        return {
            "msg_type": self.msg_type.name,
            "sequence_number": self.sequence_number,
            "ack_number": self.ack_number,
            "timestamp": self.timestamp,
            "payload_size": len(self.payload),
            "checksum": self.checksum,
            "source_id": self.source_id,
            "dest_id": self.dest_id,
        }
