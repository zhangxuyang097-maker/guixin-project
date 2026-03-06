"""状态机基类模块.

提供形式化验证所需的状态机抽象基类，
支持状态、转移和不变式的定义与检查。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum, auto


class StateType(Enum):
    """状态类型枚举."""
    
    INITIAL = auto()
    NORMAL = auto()
    ACCEPTING = auto()
    ERROR = auto()
    TIMEOUT = auto()


@dataclass
class State:
    """状态定义类.
    
    表示状态机中的一个状态，包含状态属性和不变式。
    
    Attributes:
        name: 状态名称（唯一标识）
        state_type: 状态类型
        invariants: 状态不变式列表（谓词函数）
        metadata: 额外元数据
    """
    
    name: str
    state_type: StateType = StateType.NORMAL
    invariants: list[Callable[[Any], bool]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """验证状态定义."""
        assert self.name, "状态名称不能为空"
        assert isinstance(self.state_type, StateType), "状态类型必须是 StateType 枚举"
    
    def add_invariant(self, invariant: Callable[[Any], bool]) -> None:
        """添加状态不变式.
        
        Args:
            invariant: 不变式谓词函数
        """
        self.invariants.append(invariant)
    
    def check_invariants(self, context: Any) -> tuple[bool, list[str]]:
        """检查所有不变式.
        
        Args:
            context: 验证上下文
            
        Returns:
            (是否全部满足, 违反的不变式列表)
        """
        violations = []
        for i, inv in enumerate(self.invariants):
            try:
                if not inv(context):
                    violations.append(f"invariant_{i}")
            except Exception as e:
                violations.append(f"invariant_{i}_error: {str(e)}")
        return len(violations) == 0, violations


@dataclass
class Transition:
    """状态转移定义类.
    
    表示状态机中的状态转移，包含源状态、目标状态、
    守卫条件和执行动作。
    
    Attributes:
        source: 源状态名称
        target: 目标状态名称
        guard: 守卫条件（谓词函数，可选）
        action: 转移动作（执行函数，可选）
        event: 触发事件名称（可选）
    """
    
    source: str
    target: str
    guard: Optional[Callable[[Any], bool]] = None
    action: Optional[Callable[[Any], Any]] = None
    event: Optional[str] = None
    
    def __post_init__(self) -> None:
        """验证转移定义."""
        assert self.source, "源状态不能为空"
        assert self.target, "目标状态不能为空"
    
    def is_enabled(self, context: Any) -> bool:
        """检查转移是否可触发.
        
        Args:
            context: 验证上下文
            
        Returns:
            转移是否可触发
        """
        if self.guard is None:
            return True
        try:
            return self.guard(context)
        except Exception:
            return False
    
    def execute(self, context: Any) -> Any:
        """执行转移动作.
        
        Args:
            context: 验证上下文
            
        Returns:
            动作执行结果
        """
        if self.action is not None:
            return self.action(context)
        return None


class StateMachine(ABC):
    """状态机抽象基类.
    
    提供形式化验证所需的状态机基础功能，
    所有协议模型必须继承此类。
    
    Attributes:
        _states: 状态字典（名称 -> State）
        _transitions: 转移列表
        _current_state: 当前状态名称
        _history: 状态历史记录
    """
    
    def __init__(self) -> None:
        """初始化状态机."""
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._current_state: Optional[str] = None
        self._history: list[tuple[str, Any]] = []
        self._step_count: int = 0
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化状态机.
        
        子类必须实现此方法，定义状态机的初始状态和结构。
        """
        pass
    
    def add_state(self, state: State) -> None:
        """添加状态.
        
        Args:
            state: 状态定义对象
            
        Raises:
            AssertionError: 如果状态名称已存在
        """
        assert state.name not in self._states, f"状态 '{state.name}' 已存在"
        self._states[state.name] = state
        
        # 如果是初始状态，设为当前状态
        if state.state_type == StateType.INITIAL:
            self._current_state = state.name
    
    def add_transition(self, transition: Transition) -> None:
        """添加状态转移.
        
        Args:
            transition: 转移定义对象
            
        Raises:
            AssertionError: 如果源或目标状态不存在
        """
        assert transition.source in self._states, f"源状态 '{transition.source}' 不存在"
        assert transition.target in self._states, f"目标状态 '{transition.target}' 不存在"
        self._transitions.append(transition)
    
    def get_current_state(self) -> Optional[State]:
        """获取当前状态.
        
        Returns:
            当前状态对象，如果未设置则返回 None
        """
        if self._current_state is None:
            return None
        return self._states.get(self._current_state)
    
    def get_enabled_transitions(self, context: Any) -> list[Transition]:
        """获取当前可触发的转移.
        
        Args:
            context: 验证上下文
            
        Returns:
            可触发的转移列表
        """
        if self._current_state is None:
            return []
        
        return [
            t for t in self._transitions
            if t.source == self._current_state and t.is_enabled(context)
        ]
    
    def step(self, context: Any, event: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """执行单步状态转移.
        
        Args:
            context: 验证上下文
            event: 触发事件（可选）
            
        Returns:
            (是否成功, 错误信息)
        """
        if self._current_state is None:
            return False, "当前状态未设置"
        
        # 获取可触发的转移
        enabled = self.get_enabled_transitions(context)
        
        # 如果指定了事件，筛选匹配事件的转移
        if event is not None:
            enabled = [t for t in enabled if t.event == event]
        
        if not enabled:
            return False, "没有可触发的转移"
        
        # 选择第一个可触发的转移（确定性选择）
        transition = enabled[0]
        
        # 执行转移动作
        result = transition.execute(context)
        
        # 更新当前状态
        old_state = self._current_state
        self._current_state = transition.target
        self._step_count += 1
        
        # 记录历史
        self._history.append((old_state, result))
        
        return True, None
    
    def check_invariants(self, context: Any) -> tuple[bool, list[str]]:
        """检查当前状态的所有不变式.
        
        Args:
            context: 验证上下文
            
        Returns:
            (是否全部满足, 违反的不变式列表)
        """
        current = self.get_current_state()
        if current is None:
            return False, ["当前状态未设置"]
        return current.check_invariants(context)
    
    def reset(self) -> None:
        """重置状态机到初始状态."""
        for name, state in self._states.items():
            if state.state_type == StateType.INITIAL:
                self._current_state = name
                break
        self._history.clear()
        self._step_count = 0
    
    def get_state_sequence(self) -> list[str]:
        """获取状态序列.
        
        Returns:
            状态名称列表
        """
        return [h[0] for h in self._history] + [self._current_state] if self._current_state else []
    
    def is_in_error_state(self) -> bool:
        """检查是否在错误状态.
        
        Returns:
            当前是否为错误状态
        """
        current = self.get_current_state()
        return current is not None and current.state_type == StateType.ERROR
    
    def is_in_accepting_state(self) -> bool:
        """检查是否在接受状态.
        
        Returns:
            当前是否为接受状态
        """
        current = self.get_current_state()
        return current is not None and current.state_type == StateType.ACCEPTING
    
    def get_step_count(self) -> int:
        """获取执行步数.
        
        Returns:
            已执行的步数
        """
        return self._step_count
