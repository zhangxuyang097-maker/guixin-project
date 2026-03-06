"""异常类单元测试.

测试所有自定义异常类的正确性。
"""

import pytest
from typing import Any

from core.exceptions import (
    RailCoreError,
    VerificationError,
    ProtocolViolationError,
    SimulationError,
    MemoryAccessError,
    TimeoutError,
    ConfigurationError,
    ErrorSeverity,
)


class TestRailCoreError:
    """RailCoreError 测试类."""
    
    def test_basic_error(self) -> None:
        """测试基本错误创建."""
        error = RailCoreError("测试错误")
        assert str(error) == "[RCE_RAILCOREERROR_001] ERROR: 测试错误"
        assert error.message == "测试错误"
        assert error.severity == ErrorSeverity.ERROR
    
    def test_error_with_context(self) -> None:
        """测试带上下文的错误."""
        context = {"key": "value", "number": 42}
        error = RailCoreError("测试错误", context=context)
        assert error.context == context
    
    def test_error_to_dict(self) -> None:
        """测试错误转换为字典."""
        error = RailCoreError(
            "测试错误",
            severity=ErrorSeverity.CRITICAL,
            error_code="TEST_001",
            context={"data": "value"}
        )
        
        result = error.to_dict()
        assert result["error_code"] == "TEST_001"
        assert result["severity"] == "critical"
        assert result["message"] == "测试错误"
        assert result["context"] == {"data": "value"}


class TestVerificationError:
    """VerificationError 测试类."""
    
    def test_verification_error(self) -> None:
        """测试验证错误."""
        error = VerificationError(
            "验证失败",
            solver_state="unsat"
        )
        
        assert "验证失败" in str(error)
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.context["solver_state"] == "unsat"
    
    def test_verification_error_with_custom_code(self) -> None:
        """测试带自定义错误代码的验证错误."""
        error = VerificationError(
            "验证失败",
            error_code="CUSTOM_001"
        )
        
        assert "CUSTOM_001" in str(error)


class TestProtocolViolationError:
    """ProtocolViolationError 测试类."""
    
    def test_protocol_violation(self) -> None:
        """测试协议违反错误."""
        error = ProtocolViolationError(
            "序列号错误",
            violation_type="sequence_error",
            expected_value=10,
            actual_value=20
        )
        
        assert "序列号错误" in str(error)
        assert error.context["violation_type"] == "sequence_error"
        assert error.context["expected_value"] == 10
        assert error.context["actual_value"] == 20
    
    def test_replay_detection(self) -> None:
        """测试重放检测错误."""
        error = ProtocolViolationError(
            "检测到重放消息",
            violation_type="replay_detected",
            actual_value=100
        )
        
        assert error.context["violation_type"] == "replay_detected"
        assert error.context["actual_value"] == 100


class TestSimulationError:
    """SimulationError 测试类."""
    
    def test_simulation_error(self) -> None:
        """测试仿真错误."""
        error = SimulationError(
            "非法指令",
            pc=0x1000,
            instruction=0xFFFFFFFF
        )
        
        assert "非法指令" in str(error)
        assert error.context["pc"] == 0x1000
        assert error.context["instruction"] == 0xFFFFFFFF


class TestMemoryAccessError:
    """MemoryAccessError 测试类."""
    
    def test_memory_access_error(self) -> None:
        """测试内存访问错误."""
        error = MemoryAccessError(
            "地址越界",
            address=0xFFFFFFFF,
            access_type="read"
        )
        
        assert "地址越界" in str(error)
        assert error.context["address"] == 0xFFFFFFFF
        assert error.context["access_type"] == "read"
    
    def test_pmp_violation(self) -> None:
        """测试 PMP 违反错误."""
        error = MemoryAccessError(
            "PMP 权限检查失败",
            address=0x1000,
            access_type="write",
            pmp_region=1
        )
        
        assert error.context["pmp_region"] == 1


class TestTimeoutError:
    """TimeoutError 测试类."""
    
    def test_timeout_error(self) -> None:
        """测试超时错误."""
        error = TimeoutError(
            "验证超时",
            timeout_seconds=30.0,
            operation="bmc_check"
        )
        
        assert "验证超时" in str(error)
        assert error.context["timeout_seconds"] == 30.0
        assert error.context["operation"] == "bmc_check"


class TestConfigurationError:
    """ConfigurationError 测试类."""
    
    def test_configuration_error(self) -> None:
        """测试配置错误."""
        error = ConfigurationError(
            "无效的配置参数",
            parameter="window_size"
        )
        
        assert "无效的配置参数" in str(error)
        assert error.context["parameter"] == "window_size"


class TestErrorSeverity:
    """ErrorSeverity 枚举测试类."""
    
    def test_severity_values(self) -> None:
        """测试严重级别值."""
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.FATAL.value == "fatal"
    
    def test_severity_comparison(self) -> None:
        """测试严重级别比较."""
        # 验证严重级别的顺序
        severities = [
            ErrorSeverity.WARNING,
            ErrorSeverity.ERROR,
            ErrorSeverity.CRITICAL,
            ErrorSeverity.FATAL,
        ]
        
        for i, sev in enumerate(severities):
            assert isinstance(sev, ErrorSeverity)
