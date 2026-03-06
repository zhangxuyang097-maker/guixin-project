"""协议模型模块.

实现 RSSP-I 和 RSSP-II 轨道交通信号安全通信协议的状态机模型，
支持形式化验证和仿真测试。
"""

from .rssp_i import RSSPIProtocol, RSSPIState, RSSPIConfig
from .rssp_ii import RSSPIIProtocol, RSSPIIState, RSSPIIConfig
from .message import RSSPMessage, MessageType

__all__ = [
    "RSSPIProtocol",
    "RSSPIState",
    "RSSPIConfig",
    "RSSPIIProtocol",
    "RSSPIIState",
    "RSSPIIConfig",
    "RSSPMessage",
    "MessageType",
]
