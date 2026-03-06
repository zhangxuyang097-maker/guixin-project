"""仿真模块.

提供 RISC-V RV32I 指令集模拟器和 PMP 权限检查功能，
支持协议在 RISC-V 架构下的形式化验证和仿真测试。
"""

from .riscv_simulator import RISCVSimulator, RV32IRegisters
from .pmp import PMPConfig, PMPRegion, PMPChecker
from .memory import Memory, MemoryRegion

__all__ = [
    "RISCVSimulator",
    "RV32IRegisters",
    "PMPConfig",
    "PMPRegion",
    "PMPChecker",
    "Memory",
    "MemoryRegion",
]
