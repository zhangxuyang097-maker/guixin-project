"""核心异常定义模块.

定义轨芯安项目中使用的所有自定义异常类，便于上层捕获和处理。
遵循 SIL4 安全标准要求，所有异常必须显式定义和处理。
"""

from typing import Optional, Any
from enum import Enum


class ErrorSeverity(Enum):
    """错误严重级别枚举."""
    
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class RailCoreError(Exception):
    """轨芯安基础异常类.
    
    所有自定义异常的基类，提供统一的错误信息结构。
    
    Attributes:
        message: 错误描述信息
        severity: 错误严重级别
        error_code: 错误代码（用于追溯）
        context: 额外的上下文信息
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        error_code: str = "",
        context: Optional[dict[str, Any]] = None
    ) -> None:
        """初始化异常.
        
        Args:
            message: 错误描述信息
            severity: 错误严重级别
            error_code: 错误代码
            context: 额外的上下文信息
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.error_code = error_code or self._generate_error_code()
        self.context = context or {}
    
    def _generate_error_code(self) -> str:
        """生成错误代码.
        
        Returns:
            格式化的错误代码字符串
        """
        class_name = self.__class__.__name__.upper()
        return f"RCE_{class_name}_001"
    
    def __str__(self) -> str:
        """返回格式化的错误字符串."""
        return f"[{self.error_code}] {self.severity.value.upper()}: {self.message}"
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式.
        
        Returns:
            包含错误信息的字典
        """
        return {
            "error_code": self.error_code,
            "severity": self.severity.value,
            "message": self.message,
            "context": self.context,
        }


class VerificationError(RailCoreError):
    """形式化验证错误.
    
    当验证引擎执行过程中发生错误时抛出，
    包括 Z3 求解器错误、约束冲突等。
    """
    
    def __init__(
        self,
        message: str,
        solver_state: Optional[str] = None,
        **kwargs
    ) -> None:
        """初始化验证错误.
        
        Args:
            message: 错误描述
            solver_state: 求解器状态信息
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context["solver_state"] = solver_state
        kwargs.setdefault("error_code", "RCE_VRF_001")
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            **kwargs
        )


class ProtocolViolationError(RailCoreError):
    """协议违反错误.
    
    当检测到协议规范被违反时抛出，
    包括序列号错误、超时、重放攻击等。
    """
    
    def __init__(
        self,
        message: str,
        violation_type: str = "",
        expected_value: Optional[Any] = None,
        actual_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        """初始化协议违反错误.
        
        Args:
            message: 错误描述
            violation_type: 违反类型
            expected_value: 期望值
            actual_value: 实际值
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context.update({
            "violation_type": violation_type,
            "expected_value": expected_value,
            "actual_value": actual_value,
        })
        kwargs.setdefault("error_code", "RCE_PRV_001")
        super().__init__(
            message=message,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            **kwargs
        )


class SimulationError(RailCoreError):
    """仿真执行错误.
    
    当 RISC-V 模拟器执行过程中发生错误时抛出，
    包括非法指令、内存访问越界、PMP 权限 violation 等。
    """
    
    def __init__(
        self,
        message: str,
        pc: Optional[int] = None,
        instruction: Optional[int] = None,
        **kwargs
    ) -> None:
        """初始化仿真错误.
        
        Args:
            message: 错误描述
            pc: 程序计数器值
            instruction: 当前指令
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context.update({
            "pc": pc,
            "instruction": instruction,
        })
        kwargs.setdefault("error_code", "RCE_SIM_001")
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            **kwargs
        )


class MemoryAccessError(SimulationError):
    """内存访问错误.
    
    当发生非法内存访问时抛出，包括：
    - 地址越界
    - PMP 权限检查失败
    - 未对齐访问
    """
    
    def __init__(
        self,
        message: str,
        address: int,
        access_type: str,
        pmp_region: Optional[int] = None,
        **kwargs
    ) -> None:
        """初始化内存访问错误.
        
        Args:
            message: 错误描述
            address: 访问地址
            access_type: 访问类型 (read/write/execute)
            pmp_region: 相关的 PMP 区域
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context.update({
            "address": address,
            "access_type": access_type,
            "pmp_region": pmp_region,
        })
        kwargs.setdefault("error_code", "RCE_MEM_001")
        super().__init__(
            message=message,
            context=context,
            **kwargs
        )


class TimeoutError(RailCoreError):
    """超时错误.
    
    当操作超时时抛出，包括验证超时、仿真超时等。
    """
    
    def __init__(
        self,
        message: str,
        timeout_seconds: float,
        operation: str = "",
        **kwargs
    ) -> None:
        """初始化超时错误.
        
        Args:
            message: 错误描述
            timeout_seconds: 超时时间（秒）
            operation: 超时操作名称
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context.update({
            "timeout_seconds": timeout_seconds,
            "operation": operation,
        })
        kwargs.setdefault("error_code", "RCE_TMO_001")
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            **kwargs
        )


class ConfigurationError(RailCoreError):
    """配置错误.
    
    当配置参数无效或缺失时抛出。
    """
    
    def __init__(
        self,
        message: str,
        parameter: str = "",
        **kwargs
    ) -> None:
        """初始化配置错误.
        
        Args:
            message: 错误描述
            parameter: 相关配置参数
            **kwargs: 传递给基类的参数
        """
        context = kwargs.pop("context", {})
        context["parameter"] = parameter
        kwargs.setdefault("error_code", "RCE_CFG_001")
        super().__init__(
            message=message,
            severity=ErrorSeverity.ERROR,
            context=context,
            **kwargs
        )
