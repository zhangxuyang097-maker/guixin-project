"""核心验证引擎模块.

提供基于 Z3 求解器的有界模型检测（BMC）引擎，
支持状态机形式化验证和属性规约检查。
"""

from .verification_engine import BMCEngine, VerificationResult, VerificationStatus
from .state_machine import StateMachine, State, Transition
from .exceptions import (
    RailCoreError,
    VerificationError,
    ProtocolViolationError,
    SimulationError,
    MemoryAccessError,
    TimeoutError,
    ConfigurationError,
    ErrorSeverity,
)

__all__ = [
    "BMCEngine",
    "VerificationResult",
    "VerificationStatus",
    "StateMachine",
    "State",
    "Transition",
    "RailCoreError",
    "VerificationError",
    "ProtocolViolationError",
    "SimulationError",
    "MemoryAccessError",
    "TimeoutError",
    "ConfigurationError",
    "ErrorSeverity",
]
