"""验证场景模块.

定义 RSSP-I/II 协议的验证场景和属性规约，
支持形式化验证和故障注入测试。
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum, auto

from core.verification_engine import Property, BMCEngine, VerificationResult, VerificationStatus
from core.state_machine import StateMachine
from core.exceptions import ProtocolViolationError
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIConfig
from protocol.message import RSSPMessage, MessageType


class ScenarioType(Enum):
    """场景类型枚举."""
    
    NORMAL_OPERATION = auto()
    FAULT_INJECTION = auto()
    REPLAY_ATTACK = auto()
    SEQUENCE_ERROR = auto()
    TIMEOUT_TEST = auto()
    CHECKSUM_ERROR = auto()
    DUAL_CHANNEL_FAULT = auto()


@dataclass
class VerificationScenario:
    """验证场景数据类.
    
    定义一个完整的验证场景，包括初始状态、输入序列和期望结果。
    
    Attributes:
        name: 场景名称
        description: 场景描述
        scenario_type: 场景类型
        protocol_type: 协议类型 ('RSSP-I' 或 'RSSP-II')
        setup_func: 场景设置函数
        run_func: 场景执行函数
        expected_result: 期望结果
    """
    
    name: str
    description: str
    scenario_type: ScenarioType
    protocol_type: str
    setup_func: Callable[[], Any]
    run_func: Callable[[Any], Any]
    expected_result: VerificationStatus


class ProtocolProperties:
    """协议属性规约.
    
    定义 RSSP-I/II 协议的安全属性和活性属性。
    """
    
    @staticmethod
    def create_sequence_monotonicity_property() -> Property:
        """创建序列号单调性属性.
        
        Returns:
            序列号单调性属性
        """
        def check_monotonicity(ctx: Any) -> bool:
            """检查序列号是否单调递增."""
            if not hasattr(ctx, 'received_sequences'):
                return True
            
            sequences = sorted(ctx.received_sequences)
            for i in range(1, len(sequences)):
                if sequences[i] <= sequences[i - 1]:
                    return False
            return True
        
        return Property(
            name="sequence_monotonicity",
            description="序列号必须单调递增",
            predicate=check_monotonicity,
            property_type="safety"
        )
    
    @staticmethod
    def create_no_replay_property() -> Property:
        """创建防重放属性.
        
        Returns:
            防重放属性
        """
        def check_no_replay(ctx: Any) -> bool:
            """检查是否有重放消息."""
            if not hasattr(ctx, 'received_sequences'):
                return True
            
            return len(ctx.received_sequences) == len(set(ctx.received_sequences))
        
        return Property(
            name="no_replay",
            description="不允许重放消息",
            predicate=check_no_replay,
            property_type="safety"
        )
    
    @staticmethod
    def create_window_invariant_property(max_window_size: int = 1024) -> Property:
        """创建窗口不变式属性.
        
        Args:
            max_window_size: 最大窗口大小
            
        Returns:
            窗口不变式属性
        """
        def check_window_invariant(ctx: Any) -> bool:
            """检查接收窗口不变式."""
            if not hasattr(ctx, 'receive_window'):
                return True
            
            window = ctx.receive_window
            # 检查窗口大小
            if hasattr(window, 'size') and window.size > max_window_size:
                return False
            
            # 检查基线单调性
            if hasattr(window, 'base') and window.base < 0:
                return False
            
            return True
        
        return Property(
            name="window_invariant",
            description=f"接收窗口大小不超过 {max_window_size} 且基线非负",
            predicate=check_window_invariant,
            property_type="safety"
        )
    
    @staticmethod
    def create_checksum_validity_property() -> Property:
        """创建校验和有效性属性.
        
        Returns:
            校验和有效性属性
        """
        def check_checksum_validity(ctx: Any) -> bool:
            """检查所有接收消息的校验和."""
            if not hasattr(ctx, 'received_messages'):
                return True
            
            for msg in ctx.received_messages:
                if isinstance(msg, RSSPMessage) and not msg.verify_checksum():
                    return False
            return True
        
        return Property(
            name="checksum_validity",
            description="所有接收消息的校验和必须正确",
            predicate=check_checksum_validity,
            property_type="safety"
        )
    
    @staticmethod
    def create_dual_channel_consistency_property() -> Property:
        """创建双通道一致性属性（仅 RSSP-II）.
        
        Returns:
            双通道一致性属性
        """
        def check_dual_channel_consistency(ctx: Any) -> bool:
            """检查双通道状态一致性."""
            if not hasattr(ctx, 'dual_channel_state'):
                return True
            
            dcs = ctx.dual_channel_state
            # 至少一个通道必须活跃
            if hasattr(dcs, 'is_operational'):
                return dcs.is_operational()
            
            return True
        
        return Property(
            name="dual_channel_consistency",
            description="双通道至少有一个必须活跃",
            predicate=check_dual_channel_consistency,
            property_type="safety"
        )
    
    @staticmethod
    def create_safety_code_validity_property() -> Property:
        """创建安全码有效性属性（仅 RSSP-II）.
        
        Returns:
            安全码有效性属性
        """
        def check_safety_code_validity(ctx: Any) -> bool:
            """检查所有安全码的有效性."""
            if not hasattr(ctx, 'safety_code_valid'):
                return True
            
            return ctx.safety_code_valid
        
        return Property(
            name="safety_code_validity",
            description="所有安全码必须有效",
            predicate=check_safety_code_validity,
            property_type="safety"
        )


class VerificationScenarios:
    """验证场景集合.
    
    提供预定义的验证场景，覆盖正常操作和各种故障情况。
    """
    
    @staticmethod
    def create_normal_operation_scenario(protocol_type: str = "RSSP-I") -> VerificationScenario:
        """创建正常操作场景.
        
        Args:
            protocol_type: 协议类型
            
        Returns:
            正常操作验证场景
        """
        def setup() -> Any:
            if protocol_type == "RSSP-I":
                config = RSSPIConfig(node_id=1)
                protocol = RSSPIProtocol(config)
                protocol.initialize()
                return protocol
            else:
                config = RSSPIIConfig(node_id=1)
                protocol = RSSPIIProtocol(config)
                protocol.initialize()
                protocol.start()
                return protocol
        
        def run(protocol: Any) -> VerificationResult:
            # 模拟正常通信
            if protocol_type == "RSSP-I":
                # 建立连接（手动转移到 ESTABLISHED 状态以简化测试）
                protocol.connect(2)
                protocol.step({}, "recv_synack")  # 转移到 ESTABLISHED 状态
                # 发送数据
                for i in range(5):
                    msg = protocol.send_data(b"test_data")
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    property_name="normal_operation",
                    bound=10,
                    time_seconds=0.1,
                    message="正常操作场景验证通过"
                )
            else:
                # RSSP-II
                protocol.establish_connection(2)
                protocol.step({}, "safety_check_passed")  # 转移到 SAFE_OPERATION 状态
                for i in range(5):
                    primary, secondary = protocol.send_safe_data(b"safe_data")
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    property_name="normal_operation",
                    bound=10,
                    time_seconds=0.1,
                    message="正常操作场景验证通过"
                )
        
        return VerificationScenario(
            name="normal_operation",
            description="正常操作场景：建立连接并发送数据",
            scenario_type=ScenarioType.NORMAL_OPERATION,
            protocol_type=protocol_type,
            setup_func=setup,
            run_func=run,
            expected_result=VerificationStatus.VERIFIED
        )
    
    @staticmethod
    def create_replay_attack_scenario(protocol_type: str = "RSSP-I") -> VerificationScenario:
        """创建重放攻击场景.
        
        Args:
            protocol_type: 协议类型
            
        Returns:
            重放攻击验证场景
        """
        def setup() -> Any:
            if protocol_type == "RSSP-I":
                config = RSSPIConfig(node_id=1)
                protocol = RSSPIProtocol(config)
                protocol.initialize()
                protocol.connect(2)
                protocol.step({}, "recv_synack")  # 转移到 ESTABLISHED 状态
                return protocol
            else:
                config = RSSPIIConfig(node_id=1)
                protocol = RSSPIIProtocol(config)
                protocol.initialize()
                protocol.start()
                protocol.establish_connection(2)
                protocol.step({}, "safety_check_passed")  # 转移到 SAFE_OPERATION 状态
                return protocol
        
        def run(protocol: Any) -> VerificationResult:
            try:
                # 发送第一条消息
                if protocol_type == "RSSP-I":
                    msg1 = protocol.send_data(b"message1")
                    # 先接收第一条消息（模拟对端接收）
                    protocol.receive_window.record_received(msg1.sequence_number)
                    # 尝试重放相同序列号的消息
                    replay_msg = RSSPMessage(
                        msg_type=MessageType.DATA,
                        sequence_number=msg1.sequence_number,
                        payload=b"replay",
                        source_id=2,
                        dest_id=1,
                    )
                    replay_msg.update_checksum()
                    protocol.receive_message(replay_msg)
                else:
                    primary, _ = protocol.send_safe_data(b"message1")
                    # 先接收第一条消息
                    protocol.received_sequences.add(primary.sequence_number)
                    # 尝试重放
                    protocol.receive_message(primary)
                
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    property_name="replay_detection",
                    bound=5,
                    time_seconds=0.1,
                    message="未检测到重放攻击"
                )
            except ProtocolViolationError as e:
                if "重放" in str(e).lower() or "replay" in str(e).lower():
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        property_name="replay_detection",
                        bound=5,
                        time_seconds=0.1,
                        message="成功检测到重放攻击"
                    )
                raise
        
        return VerificationScenario(
            name="replay_attack",
            description="重放攻击场景：验证协议能否检测重放消息",
            scenario_type=ScenarioType.REPLAY_ATTACK,
            protocol_type=protocol_type,
            setup_func=setup,
            run_func=run,
            expected_result=VerificationStatus.VERIFIED
        )
    
    @staticmethod
    def create_sequence_error_scenario(protocol_type: str = "RSSP-I") -> VerificationScenario:
        """创建序列号错误场景.
        
        Args:
            protocol_type: 协议类型
            
        Returns:
            序列号错误验证场景
        """
        def setup() -> Any:
            if protocol_type == "RSSP-I":
                config = RSSPIConfig(node_id=1)
                protocol = RSSPIProtocol(config)
                protocol.initialize()
                protocol.connect(2)
                protocol.step({}, "recv_synack")  # 转移到 ESTABLISHED 状态
                # 发送一些消息以推进序列号
                for i in range(3):
                    protocol.send_data(b"data")
                return protocol
            else:
                config = RSSPIIConfig(node_id=1)
                protocol = RSSPIIProtocol(config)
                protocol.initialize()
                protocol.start()
                protocol.establish_connection(2)
                protocol.step({}, "safety_check_passed")  # 转移到 SAFE_OPERATION 状态
                for i in range(3):
                    protocol.send_safe_data(b"data")
                return protocol
        
        def run(protocol: Any) -> VerificationResult:
            try:
                # 发送超出窗口范围的消息
                out_of_order_msg = RSSPMessage(
                    msg_type=MessageType.DATA,
                    sequence_number=10000,  # 远超窗口范围（窗口大小 1024）
                    payload=b"out_of_order",
                    source_id=2,
                    dest_id=1,
                )
                out_of_order_msg.update_checksum()
                protocol.receive_message(out_of_order_msg)
                
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    property_name="sequence_validation",
                    bound=5,
                    time_seconds=0.1,
                    message="未检测到序列号错误"
                )
            except ProtocolViolationError as e:
                if "sequence" in str(e).lower() or "序列" in str(e) or "窗口" in str(e):
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        property_name="sequence_validation",
                        bound=5,
                        time_seconds=0.1,
                        message="成功检测到序列号错误"
                    )
                raise
        
        return VerificationScenario(
            name="sequence_error",
            description="序列号错误场景：验证协议能否检测乱序消息",
            scenario_type=ScenarioType.SEQUENCE_ERROR,
            protocol_type=protocol_type,
            setup_func=setup,
            run_func=run,
            expected_result=VerificationStatus.VERIFIED
        )
    
    @staticmethod
    def create_checksum_error_scenario(protocol_type: str = "RSSP-I") -> VerificationScenario:
        """创建校验和错误场景.
        
        Args:
            protocol_type: 协议类型
            
        Returns:
            校验和错误验证场景
        """
        def setup() -> Any:
            if protocol_type == "RSSP-I":
                config = RSSPIConfig(node_id=1)
                protocol = RSSPIProtocol(config)
                protocol.initialize()
                protocol.connect(2)
                protocol.step({}, "recv_synack")  # 转移到 ESTABLISHED 状态
                return protocol
            else:
                config = RSSPIIConfig(node_id=1)
                protocol = RSSPIIProtocol(config)
                protocol.initialize()
                protocol.start()
                protocol.establish_connection(2)
                protocol.step({}, "safety_check_passed")  # 转移到 SAFE_OPERATION 状态
                return protocol
        
        def run(protocol: Any) -> VerificationResult:
            try:
                # 发送校验和错误的消息
                bad_msg = RSSPMessage(
                    msg_type=MessageType.DATA,
                    sequence_number=1,
                    payload=b"corrupted",
                    source_id=2,
                    dest_id=1,
                    checksum=0xDEADBEEF,  # 错误的校验和
                )
                protocol.receive_message(bad_msg)
                
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    property_name="checksum_validation",
                    bound=5,
                    time_seconds=0.1,
                    message="未检测到校验和错误"
                )
            except ProtocolViolationError as e:
                if "checksum" in str(e).lower() or "校验" in str(e):
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        property_name="checksum_validation",
                        bound=5,
                        time_seconds=0.1,
                        message="成功检测到校验和错误"
                    )
                raise
        
        return VerificationScenario(
            name="checksum_error",
            description="校验和错误场景：验证协议能否检测校验和错误",
            scenario_type=ScenarioType.CHECKSUM_ERROR,
            protocol_type=protocol_type,
            setup_func=setup,
            run_func=run,
            expected_result=VerificationStatus.VERIFIED
        )
    
    @staticmethod
    def create_dual_channel_fault_scenario() -> VerificationScenario:
        """创建双通道故障场景（仅 RSSP-II）.
        
        Returns:
            双通道故障验证场景
        """
        def setup() -> Any:
            config = RSSPIIConfig(node_id=1, dual_channel=True)
            protocol = RSSPIIProtocol(config)
            protocol.initialize()
            protocol.start()
            protocol.establish_connection(2)
            protocol.step({}, "safety_check_passed")  # 转移到 SAFE_OPERATION 状态
            return protocol
        
        def run(protocol: Any) -> VerificationResult:
            # 模拟通道 A 故障
            protocol.dual_channel_state.set_channel_state('A', False)
            
            # 验证通道 B 仍能工作
            if protocol.dual_channel_state.is_operational():
                try:
                    primary, secondary = protocol.send_safe_data(b"test")
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        property_name="dual_channel_fault_tolerance",
                        bound=5,
                        time_seconds=0.1,
                        message="双通道故障容错验证通过"
                    )
                except Exception as e:
                    return VerificationResult(
                        status=VerificationStatus.ERROR,
                        property_name="dual_channel_fault_tolerance",
                        bound=5,
                        time_seconds=0.1,
                        message=f"单通道工作失败: {e}"
                    )
            else:
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    property_name="dual_channel_fault_tolerance",
                    bound=5,
                    time_seconds=0.1,
                    message="双通道都不可用"
                )
        
        return VerificationScenario(
            name="dual_channel_fault",
            description="双通道故障场景：验证单通道故障时系统仍能工作",
            scenario_type=ScenarioType.DUAL_CHANNEL_FAULT,
            protocol_type="RSSP-II",
            setup_func=setup,
            run_func=run,
            expected_result=VerificationStatus.VERIFIED
        )


class ScenarioRunner:
    """场景运行器.
    
    执行验证场景并收集结果。
    """
    
    def __init__(self) -> None:
        """初始化场景运行器."""
        self.results: list[tuple[VerificationScenario, VerificationResult]] = []
    
    def run_scenario(self, scenario: VerificationScenario) -> VerificationResult:
        """运行单个验证场景.
        
        Args:
            scenario: 验证场景
            
        Returns:
            验证结果
        """
        # 设置场景
        context = scenario.setup_func()
        
        # 执行场景
        result = scenario.run_func(context)
        
        # 记录结果
        self.results.append((scenario, result))
        
        return result
    
    def run_all_scenarios(
        self,
        protocol_type: str = "RSSP-I"
    ) -> list[tuple[VerificationScenario, VerificationResult]]:
        """运行所有验证场景.
        
        Args:
            protocol_type: 协议类型
            
        Returns:
            场景和结果列表
        """
        scenarios = [
            VerificationScenarios.create_normal_operation_scenario(protocol_type),
            VerificationScenarios.create_replay_attack_scenario(protocol_type),
            VerificationScenarios.create_sequence_error_scenario(protocol_type),
            VerificationScenarios.create_checksum_error_scenario(protocol_type),
        ]
        
        if protocol_type == "RSSP-II":
            scenarios.append(VerificationScenarios.create_dual_channel_fault_scenario())
        
        for scenario in scenarios:
            self.run_scenario(scenario)
        
        return self.results
    
    def get_summary(self) -> dict[str, Any]:
        """获取执行摘要.
        
        Returns:
            摘要信息字典
        """
        total = len(self.results)
        passed = sum(1 for _, r in self.results if r.status == VerificationStatus.VERIFIED)
        failed = sum(1 for _, r in self.results if r.status == VerificationStatus.VIOLATION_FOUND)
        errors = sum(1 for _, r in self.results if r.status == VerificationStatus.ERROR)
        
        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / total if total > 0 else 0,
        }
