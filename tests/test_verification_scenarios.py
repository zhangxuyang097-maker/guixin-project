"""验证场景单元测试.

测试验证场景和属性规约的正确性。
"""

import pytest
from typing import Any

from core.verification_scenarios import (
    VerificationScenarios,
    ProtocolProperties,
    ScenarioRunner,
    VerificationScenario,
)
from core.verification_engine import VerificationStatus, Property
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIConfig


class TestProtocolProperties:
    """ProtocolProperties 测试类."""
    
    def test_sequence_monotonicity_property(self) -> None:
        """测试序列号单调性属性."""
        prop = ProtocolProperties.create_sequence_monotonicity_property()
        
        assert prop.name == "sequence_monotonicity"
        assert prop.property_type == "safety"
        
        # 测试满足条件（已排序的序列）
        class MockContext:
            received_sequences = [1, 2, 3, 4, 5]
        
        assert prop.check(MockContext()) is True
        
        # 测试违反条件（有重复序列号）
        class MockContextBad:
            received_sequences = [1, 2, 2, 3, 4]  # 重复的 2
        
        assert prop.check(MockContextBad()) is False
    
    def test_no_replay_property(self) -> None:
        """测试防重放属性."""
        prop = ProtocolProperties.create_no_replay_property()
        
        assert prop.name == "no_replay"
        
        # 测试无重放
        class MockContext:
            received_sequences = {1, 2, 3, 4, 5}
        
        assert prop.check(MockContext()) is True
        
        # 测试有重放（集合自动去重，所以这里用列表模拟）
        # 实际场景中 received_sequences 应该是集合
    
    def test_window_invariant_property(self) -> None:
        """测试窗口不变式属性."""
        prop = ProtocolProperties.create_window_invariant_property(max_window_size=1024)
        
        assert prop.name == "window_invariant"
        
        # 测试满足条件
        class MockWindow:
            size = 512
            base = 0
        
        class MockContext:
            receive_window = MockWindow()
        
        assert prop.check(MockContext()) is True
    
    def test_checksum_validity_property(self) -> None:
        """测试校验和有效性属性."""
        prop = ProtocolProperties.create_checksum_validity_property()
        
        assert prop.name == "checksum_validity"
    
    def test_dual_channel_consistency_property(self) -> None:
        """测试双通道一致性属性."""
        prop = ProtocolProperties.create_dual_channel_consistency_property()
        
        assert prop.name == "dual_channel_consistency"
        
        # 测试双通道正常
        class MockDualChannel:
            def is_operational(self):
                return True
        
        class MockContext:
            dual_channel_state = MockDualChannel()
        
        assert prop.check(MockContext()) is True


class TestVerificationScenarios:
    """VerificationScenarios 测试类."""
    
    def test_normal_operation_scenario_rssp_i(self) -> None:
        """测试 RSSP-I 正常操作场景."""
        scenario = VerificationScenarios.create_normal_operation_scenario("RSSP-I")
        
        assert scenario.name == "normal_operation"
        assert scenario.protocol_type == "RSSP-I"
        assert scenario.expected_result == VerificationStatus.VERIFIED
        
        # 运行场景
        context = scenario.setup_func()
        assert isinstance(context, RSSPIProtocol)
        
        result = scenario.run_func(context)
        assert result.status == VerificationStatus.VERIFIED
    
    def test_normal_operation_scenario_rssp_ii(self) -> None:
        """测试 RSSP-II 正常操作场景."""
        scenario = VerificationScenarios.create_normal_operation_scenario("RSSP-II")
        
        assert scenario.name == "normal_operation"
        assert scenario.protocol_type == "RSSP-II"
        
        # 运行场景
        context = scenario.setup_func()
        assert isinstance(context, RSSPIIProtocol)
        
        result = scenario.run_func(context)
        assert result.status == VerificationStatus.VERIFIED
    
    def test_replay_attack_scenario(self) -> None:
        """测试重放攻击场景."""
        scenario = VerificationScenarios.create_replay_attack_scenario("RSSP-I")
        
        assert scenario.name == "replay_attack"
        assert scenario.scenario_type.name == "REPLAY_ATTACK"
        
        # 运行场景
        context = scenario.setup_func()
        result = scenario.run_func(context)
        
        # 应该检测到重放攻击
        assert result.status == VerificationStatus.VERIFIED
        assert "重放" in result.message or "replay" in result.message.lower()
    
    def test_sequence_error_scenario(self) -> None:
        """测试序列号错误场景."""
        scenario = VerificationScenarios.create_sequence_error_scenario("RSSP-I")
        
        assert scenario.name == "sequence_error"
        
        # 运行场景
        context = scenario.setup_func()
        result = scenario.run_func(context)
        
        # 应该检测到序列号错误
        assert result.status == VerificationStatus.VERIFIED
    
    def test_checksum_error_scenario(self) -> None:
        """测试校验和错误场景."""
        scenario = VerificationScenarios.create_checksum_error_scenario("RSSP-I")
        
        assert scenario.name == "checksum_error"
        
        # 运行场景
        context = scenario.setup_func()
        result = scenario.run_func(context)
        
        # 应该检测到校验和错误
        assert result.status == VerificationStatus.VERIFIED
    
    def test_dual_channel_fault_scenario(self) -> None:
        """测试双通道故障场景."""
        scenario = VerificationScenarios.create_dual_channel_fault_scenario()
        
        assert scenario.name == "dual_channel_fault"
        assert scenario.protocol_type == "RSSP-II"
        
        # 运行场景
        context = scenario.setup_func()
        result = scenario.run_func(context)
        
        # 应该验证通过（单通道故障容错）
        assert result.status == VerificationStatus.VERIFIED


class TestScenarioRunner:
    """ScenarioRunner 测试类."""
    
    def test_runner_creation(self) -> None:
        """测试运行器创建."""
        runner = ScenarioRunner()
        
        assert runner.results == []
    
    def test_run_single_scenario(self) -> None:
        """测试运行单个场景."""
        runner = ScenarioRunner()
        
        scenario = VerificationScenarios.create_normal_operation_scenario("RSSP-I")
        result = runner.run_scenario(scenario)
        
        assert len(runner.results) == 1
        assert result.status == VerificationStatus.VERIFIED
    
    def test_run_all_scenarios(self) -> None:
        """测试运行所有场景."""
        runner = ScenarioRunner()
        
        results = runner.run_all_scenarios("RSSP-I")
        
        assert len(results) > 0
        
        # 检查摘要
        summary = runner.get_summary()
        assert summary["total_scenarios"] == len(results)
        assert summary["passed"] > 0
    
    def test_get_summary(self) -> None:
        """测试获取摘要."""
        runner = ScenarioRunner()
        
        # 运行一些场景
        scenario1 = VerificationScenarios.create_normal_operation_scenario("RSSP-I")
        runner.run_scenario(scenario1)
        
        summary = runner.get_summary()
        
        assert "total_scenarios" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "errors" in summary
        assert "pass_rate" in summary


class TestPropertyIntegration:
    """属性集成测试类."""
    
    def test_property_with_protocol(self) -> None:
        """测试属性与协议集成."""
        # 创建协议实例
        config = RSSPIConfig(node_id=1)
        protocol = RSSPIProtocol(config)
        
        # 创建属性
        prop = ProtocolProperties.create_sequence_monotonicity_property()
        
        # 使用协议作为上下文检查属性
        # 注意：实际使用时可能需要包装协议对象
    
    def test_all_properties_with_rssp_i(self) -> None:
        """测试所有属性与 RSSP-I."""
        properties = [
            ProtocolProperties.create_sequence_monotonicity_property(),
            ProtocolProperties.create_no_replay_property(),
            ProtocolProperties.create_window_invariant_property(),
            ProtocolProperties.create_checksum_validity_property(),
        ]
        
        # 创建协议实例
        config = RSSPIConfig(node_id=1)
        protocol = RSSPIProtocol(config)
        
        # 验证所有属性
        for prop in properties:
            assert isinstance(prop, Property)
            assert prop.name is not None
    
    def test_all_properties_with_rssp_ii(self) -> None:
        """测试所有属性与 RSSP-II."""
        properties = [
            ProtocolProperties.create_sequence_monotonicity_property(),
            ProtocolProperties.create_no_replay_property(),
            ProtocolProperties.create_window_invariant_property(),
            ProtocolProperties.create_checksum_validity_property(),
            ProtocolProperties.create_dual_channel_consistency_property(),
            ProtocolProperties.create_safety_code_validity_property(),
        ]
        
        # 创建协议实例
        config = RSSPIIConfig(node_id=1)
        protocol = RSSPIIProtocol(config)
        
        # 验证所有属性
        for prop in properties:
            assert isinstance(prop, Property)
            assert prop.name is not None
