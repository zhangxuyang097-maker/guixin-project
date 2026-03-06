"""轨芯安 (RailCore Secure) - 轨道交通信号安全协议形式化验证工具.

面向国产 RISC-V 架构的轨道交通信号安全协议轻量化形式化验证工具，
实现 RSSP-I/II 协议在 RISC-V 环境下的轻量化验证，满足 SIL4 级安全要求。

Author: RailCore Secure Team
Version: 1.0.0
License: MIT
"""

__version__ = "1.0.0"
__author__ = "RailCore Secure Team"

from core.verification_engine import BMCEngine, VerificationResult
from protocol.rssp_i import RSSPIProtocol, RSSPIState
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIState
from simulation.riscv_simulator import RISCVSimulator

__all__ = [
    "BMCEngine",
    "VerificationResult", 
    "RSSPIProtocol",
    "RSSPIState",
    "RSSPIIProtocol",
    "RSSPIIState",
    "RISCVSimulator",
]
