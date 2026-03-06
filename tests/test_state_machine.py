"""状态机模块单元测试.

测试状态机基类的正确性。
"""

import pytest
from typing import Any

from core.state_machine import StateMachine, State, StateType, Transition


class TestState:
    """State 类测试."""
    
    def test_state_creation(self) -> None:
        """测试状态创建."""
        state = State("TEST", StateType.NORMAL)
        assert state.name == "TEST"
        assert state.state_type == StateType.NORMAL
        assert state.invariants == []
    
    def test_state_with_invariants(self) -> None:
        """测试带不变式的状态."""
        state = State("TEST", StateType.NORMAL)
        
        # 添加不变式
        state.add_invariant(lambda ctx: True)
        state.add_invariant(lambda ctx: len(ctx) > 0)
        
        assert len(state.invariants) == 2
    
    def test_check_invariants(self) -> None:
        """测试不变式检查."""
        state = State("TEST", StateType.NORMAL)
        
        # 添加不变式
        state.add_invariant(lambda ctx: ctx["valid"])
        
        # 检查满足不变式
        passed, violations = state.check_invariants({"valid": True})
        assert passed is True
        assert violations == []
        
        # 检查违反不变式
        passed, violations = state.check_invariants({"valid": False})
        assert passed is False
        assert len(violations) == 1
    
    def test_initial_state(self) -> None:
        """测试初始状态."""
        state = State("INIT", StateType.INITIAL)
        assert state.state_type == StateType.INITIAL


class TestTransition:
    """Transition 类测试."""
    
    def test_transition_creation(self) -> None:
        """测试转移创建."""
        trans = Transition("A", "B")
        assert trans.source == "A"
        assert trans.target == "B"
        assert trans.guard is None
        assert trans.action is None
    
    def test_transition_with_guard(self) -> None:
        """测试带守卫的转移."""
        trans = Transition("A", "B", guard=lambda ctx: ctx["ready"])
        
        assert trans.is_enabled({"ready": True}) is True
        assert trans.is_enabled({"ready": False}) is False
    
    def test_transition_with_action(self) -> None:
        """测试带动作的转移."""
        trans = Transition("A", "B", action=lambda ctx: {"result": "success"})
        
        result = trans.execute({})
        assert result == {"result": "success"}


class SimpleStateMachine(StateMachine):
    """简单状态机（用于测试）."""
    
    def __init__(self) -> None:
        super().__init__()
        self.initialize()
    
    def initialize(self) -> None:
        """初始化简单状态机."""
        # 添加状态
        self.add_state(State("IDLE", StateType.INITIAL))
        self.add_state(State("RUNNING", StateType.NORMAL))
        self.add_state(State("STOPPED", StateType.ACCEPTING))
        self.add_state(State("ERROR", StateType.ERROR))
        
        # 添加转移
        self.add_transition(Transition("IDLE", "RUNNING", event="start"))
        self.add_transition(Transition("RUNNING", "STOPPED", event="stop"))
        self.add_transition(Transition("RUNNING", "ERROR", event="error"))
        self.add_transition(Transition("ERROR", "IDLE", event="reset"))


class TestStateMachine:
    """StateMachine 类测试."""
    
    def test_state_machine_creation(self) -> None:
        """测试状态机创建."""
        sm = SimpleStateMachine()
        
        assert len(sm._states) == 4
        assert len(sm._transitions) == 4
    
    def test_initial_state(self) -> None:
        """测试初始状态."""
        sm = SimpleStateMachine()
        
        current = sm.get_current_state()
        assert current is not None
        assert current.name == "IDLE"
        assert current.state_type == StateType.INITIAL
    
    def test_state_transition(self) -> None:
        """测试状态转移."""
        sm = SimpleStateMachine()
        
        # 初始状态
        assert sm.get_current_state().name == "IDLE"
        
        # 执行转移
        success, error = sm.step({}, "start")
        assert success is True
        assert error is None
        
        # 验证新状态
        assert sm.get_current_state().name == "RUNNING"
    
    def test_invalid_transition(self) -> None:
        """测试无效转移."""
        sm = SimpleStateMachine()
        
        # 从 IDLE 状态尝试执行 stop（无效）
        success, error = sm.step({}, "stop")
        assert success is False
        assert error is not None
    
    def test_get_enabled_transitions(self) -> None:
        """测试获取可触发转移."""
        sm = SimpleStateMachine()
        
        # IDLE 状态的可触发转移
        enabled = sm.get_enabled_transitions({})
        assert len(enabled) == 1
        assert enabled[0].event == "start"
    
    def test_reset(self) -> None:
        """测试重置状态机."""
        sm = SimpleStateMachine()
        
        # 执行一些转移
        sm.step({}, "start")
        assert sm.get_current_state().name == "RUNNING"
        
        # 重置
        sm.reset()
        assert sm.get_current_state().name == "IDLE"
        assert sm.get_step_count() == 0
    
    def test_state_sequence(self) -> None:
        """测试状态序列."""
        sm = SimpleStateMachine()
        
        # 执行转移序列
        sm.step({}, "start")
        sm.step({}, "stop")
        
        sequence = sm.get_state_sequence()
        assert sequence == ["IDLE", "RUNNING", "STOPPED"]
    
    def test_is_in_error_state(self) -> None:
        """测试错误状态检查."""
        sm = SimpleStateMachine()
        
        assert sm.is_in_error_state() is False
        
        sm.step({}, "start")
        sm.step({}, "error")
        
        assert sm.is_in_error_state() is True
    
    def test_is_in_accepting_state(self) -> None:
        """测试接受状态检查."""
        sm = SimpleStateMachine()
        
        assert sm.is_in_accepting_state() is False
        
        sm.step({}, "start")
        sm.step({}, "stop")
        
        assert sm.is_in_accepting_state() is True
    
    def test_duplicate_state(self) -> None:
        """测试重复状态."""
        sm = SimpleStateMachine()
        
        with pytest.raises(AssertionError):
            sm.add_state(State("IDLE", StateType.NORMAL))
    
    def test_invalid_transition_source(self) -> None:
        """测试无效转移源状态."""
        sm = SimpleStateMachine()
        
        with pytest.raises(AssertionError):
            sm.add_transition(Transition("INVALID", "IDLE"))
