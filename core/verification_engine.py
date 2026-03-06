"""形式化验证引擎模块.

实现基于 Z3 求解器的有界模型检测（BMC）引擎，
支持状态机形式化验证、属性规约检查和反例生成。
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Any, Iterator
from collections.abc import Generator

from z3 import (
    Solver, Bool, Int, BitVec, BitVecVal, And, Or, Not, Implies,
    sat, unsat, unknown, ModelRef, ExprRef, CheckSatResult,
    simplify, substitute
)

from .exceptions import VerificationError, TimeoutError, ErrorSeverity
from .state_machine import StateMachine, State, StateType


class VerificationStatus(Enum):
    """验证状态枚举."""
    
    VERIFIED = auto()
    VIOLATION_FOUND = auto()
    TIMEOUT = auto()
    ERROR = auto()
    UNKNOWN = auto()


@dataclass
class CounterExample:
    """反例数据类.
    
    当验证发现属性违反时，记录反例信息。
    
    Attributes:
        step: 违反发生的步数
        state: 违反时的状态
        variable_values: 变量赋值
        trace: 执行轨迹
    """
    
    step: int
    state: str
    variable_values: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式."""
        return {
            "step": self.step,
            "state": self.state,
            "variable_values": self.variable_values,
            "trace": self.trace,
        }


@dataclass
class VerificationResult:
    """验证结果数据类.
    
    记录验证执行的结果信息。
    
    Attributes:
        status: 验证状态
        property_name: 验证的属性名称
        bound: 验证边界（最大步数）
        time_seconds: 验证耗时（秒）
        counter_example: 反例（如果有）
        solver_stats: 求解器统计信息
        message: 结果描述信息
    """
    
    status: VerificationStatus
    property_name: str
    bound: int
    time_seconds: float
    counter_example: Optional[CounterExample] = None
    solver_stats: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    
    def is_verified(self) -> bool:
        """检查是否验证通过."""
        return self.status == VerificationStatus.VERIFIED
    
    def has_violation(self) -> bool:
        """检查是否发现违反."""
        return self.status == VerificationStatus.VIOLATION_FOUND
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式."""
        return {
            "status": self.status.name,
            "property_name": self.property_name,
            "bound": self.bound,
            "time_seconds": self.time_seconds,
            "counter_example": self.counter_example.to_dict() if self.counter_example else None,
            "solver_stats": self.solver_stats,
            "message": self.message,
        }


class Property:
    """属性规约类.
    
    定义要验证的安全属性或活性属性。
    
    Attributes:
        name: 属性名称
        description: 属性描述
        predicate: 属性谓词函数
        property_type: 属性类型（safety/liveness）
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        predicate: Callable[[Any], bool],
        property_type: str = "safety"
    ) -> None:
        """初始化属性规约.
        
        Args:
            name: 属性名称
            description: 属性描述
            predicate: 属性谓词函数
            property_type: 属性类型
        """
        self.name = name
        self.description = description
        self.predicate = predicate
        self.property_type = property_type
        
        assert self.name, "属性名称不能为空"
        assert self.property_type in ("safety", "liveness"), "属性类型必须是 safety 或 liveness"
    
    def check(self, context: Any) -> bool:
        """检查属性.
        
        Args:
            context: 验证上下文
            
        Returns:
            属性是否满足
        """
        try:
            return self.predicate(context)
        except Exception as e:
            raise VerificationError(
                f"属性检查失败: {str(e)}",
                error_code="RCE_PRP_001"
            )


class BMCEngine:
    """有界模型检测引擎.
    
    基于 Z3 求解器实现 BMC 算法，支持：
    - 状态机展开
    - 属性规约检查
    - 反例生成
    - 增量求解
    
    Attributes:
        solver: Z3 求解器实例
        timeout_ms: 超时时间（毫秒）
        properties: 要验证的属性列表
        _statistics: 统计信息
    """
    
    def __init__(self, timeout_ms: int = 30000) -> None:
        """初始化 BMC 引擎.
        
        Args:
            timeout_ms: 求解器超时时间（毫秒），默认 30 秒
        """
        self.solver = Solver()
        self.timeout_ms = timeout_ms
        self.properties: list[Property] = []
        self._statistics: dict[str, Any] = {
            "total_checks": 0,
            "sat_results": 0,
            "unsat_results": 0,
            "unknown_results": 0,
            "total_time_ms": 0,
        }
        
        # 设置求解器超时
        self.solver.set("timeout", timeout_ms)
    
    def add_property(self, prop: Property) -> None:
        """添加要验证的属性.
        
        Args:
            prop: 属性规约对象
        """
        self.properties.append(prop)
    
    def reset(self) -> None:
        """重置求解器状态."""
        self.solver.reset()
    
    def create_bitvec_var(
        self,
        name: str,
        size: int = 32
    ) -> BitVec:
        """创建位向量变量.
        
        Args:
            name: 变量名称
            size: 位宽（默认 32 位）
            
        Returns:
            Z3 位向量变量
        """
        return BitVec(name, size)
    
    def create_int_var(self, name: str) -> Int:
        """创建整数变量.
        
        Args:
            name: 变量名称
            
        Returns:
            Z3 整数变量
        """
        return Int(name)
    
    def create_bool_var(self, name: str) -> Bool:
        """创建布尔变量.
        
        Args:
            name: 变量名称
            
        Returns:
            Z3 布尔变量
        """
        return Bool(name)
    
    def encode_state_machine(
        self,
        state_machine: StateMachine,
        bound: int,
        context_builder: Optional[Callable[[int], Any]] = None
    ) -> list[ExprRef]:
        """编码状态机为 Z3 约束.
        
        将状态机展开为指定步数的约束公式。
        
        Args:
            state_machine: 状态机实例
            bound: 展开边界（步数）
            context_builder: 上下文构建函数
            
        Returns:
            Z3 约束表达式列表
        """
        constraints = []
        
        # 初始状态约束
        initial_state = None
        for name, state in state_machine._states.items():
            if state.state_type == StateType.INITIAL:
                initial_state = name
                break
        
        if initial_state is None:
            raise VerificationError(
                "状态机没有初始状态",
                error_code="RCE_BMC_001"
            )
        
        # 创建状态变量序列
        state_vars = [
            self.create_int_var(f"state_{i}")
            for i in range(bound + 1)
        ]
        
        # 初始状态约束
        state_map = {name: i for i, name in enumerate(state_machine._states.keys())}
        constraints.append(state_vars[0] == state_map[initial_state])
        
        # 状态转移约束
        for i in range(bound):
            transition_constraints = []
            for trans in state_machine._transitions:
                src_idx = state_map[trans.source]
                tgt_idx = state_map[trans.target]
                # 如果当前状态是源状态，则下一状态可以是目标状态
                transition_constraints.append(
                    Implies(state_vars[i] == src_idx, state_vars[i + 1] == tgt_idx)
                )
            
            if transition_constraints:
                constraints.append(And(*transition_constraints))
        
        return constraints
    
    def verify_state_machine(
        self,
        state_machine: StateMachine,
        bound: int = 10,
        property_name: Optional[str] = None
    ) -> VerificationResult:
        """验证状态机.
        
        使用 BMC 算法验证状态机在给定边界内是否满足所有属性。
        
        Args:
            state_machine: 状态机实例
            bound: 验证边界（步数）
            property_name: 指定验证的属性名称（可选）
            
        Returns:
            验证结果
        """
        start_time = time.perf_counter()
        
        try:
            # 编码状态机
            constraints = self.encode_state_machine(state_machine, bound)
            
            # 添加约束到求解器
            for constraint in constraints:
                self.solver.add(constraint)
            
            # 选择要验证的属性
            props_to_check = self.properties
            if property_name:
                props_to_check = [p for p in self.properties if p.name == property_name]
                if not props_to_check:
                    return VerificationResult(
                        status=VerificationStatus.ERROR,
                        property_name=property_name,
                        bound=bound,
                        time_seconds=time.perf_counter() - start_time,
                        message=f"未找到属性: {property_name}"
                    )
            
            # 逐属性验证
            for prop in props_to_check:
                # 创建属性违反条件
                prop_violation = self._encode_property_violation(prop, bound)
                
                # 临时添加属性违反条件
                self.solver.push()
                self.solver.add(prop_violation)
                
                # 求解
                self._statistics["total_checks"] += 1
                check_start = time.perf_counter()
                result = self.solver.check()
                check_time = time.perf_counter() - check_start
                self._statistics["total_time_ms"] += check_time * 1000
                
                if result == sat:
                    # 发现属性违反
                    self._statistics["sat_results"] += 1
                    model = self.solver.model()
                    counter_example = self._extract_counter_example(model, bound, state_machine)
                    
                    self.solver.pop()
                    
                    return VerificationResult(
                        status=VerificationStatus.VIOLATION_FOUND,
                        property_name=prop.name,
                        bound=bound,
                        time_seconds=time.perf_counter() - start_time,
                        counter_example=counter_example,
                        solver_stats=dict(self._statistics),
                        message=f"发现属性违反: {prop.description}"
                    )
                
                elif result == unsat:
                    # 属性满足
                    self._statistics["unsat_results"] += 1
                    self.solver.pop()
                    continue
                
                else:
                    # 未知结果
                    self._statistics["unknown_results"] += 1
                    self.solver.pop()
                    return VerificationResult(
                        status=VerificationStatus.UNKNOWN,
                        property_name=prop.name,
                        bound=bound,
                        time_seconds=time.perf_counter() - start_time,
                        solver_stats=dict(self._statistics),
                        message="求解器返回未知结果"
                    )
            
            # 所有属性都满足
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                property_name=property_name or "all_properties",
                bound=bound,
                time_seconds=time.perf_counter() - start_time,
                solver_stats=dict(self._statistics),
                message="所有属性验证通过"
            )
        
        except Exception as e:
            if isinstance(e, VerificationError):
                raise
            raise VerificationError(
                f"验证过程出错: {str(e)}",
                error_code="RCE_BMC_002"
            )
    
    def _encode_property_violation(
        self,
        prop: Property,
        bound: int
    ) -> ExprRef:
        """编码属性违反条件.
        
        Args:
            prop: 属性规约
            bound: 边界
            
        Returns:
            属性违反的 Z3 表达式
        """
        # 对于安全属性，编码为在某一步违反
        # 这里简化处理，实际应根据属性类型编码
        violation_var = self.create_bool_var(f"violation_{prop.name}")
        return violation_var
    
    def _extract_counter_example(
        self,
        model: ModelRef,
        bound: int,
        state_machine: StateMachine
    ) -> CounterExample:
        """从模型中提取反例.
        
        Args:
            model: Z3 模型
            bound: 边界
            state_machine: 状态机实例
            
        Returns:
            反例对象
        """
        variable_values = {}
        trace = []
        
        # 提取变量赋值
        for decl in model.decls():
            try:
                value = model[decl()]
                variable_values[str(decl.name())] = str(value)
            except Exception:
                pass
        
        # 提取状态轨迹
        for i in range(bound + 1):
            state_var_name = f"state_{i}"
            try:
                state_var = Int(state_var_name)
                value = model.eval(state_var)
                trace.append({"step": i, "state": str(value)})
            except Exception:
                pass
        
        return CounterExample(
            step=bound,
            state="unknown",
            variable_values=variable_values,
            trace=trace
        )
    
    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息.
        
        Returns:
            统计信息字典
        """
        return dict(self._statistics)
    
    def verify_incremental(
        self,
        state_machine: StateMachine,
        min_bound: int = 1,
        max_bound: int = 100,
        property_name: Optional[str] = None
    ) -> Generator[VerificationResult, None, None]:
        """增量式验证.
        
        从最小边界开始，逐步增加边界进行验证，
        适用于寻找最小反例。
        
        Args:
            state_machine: 状态机实例
            min_bound: 最小边界
            max_bound: 最大边界
            property_name: 指定验证的属性名称
            
        Yields:
            每一步的验证结果
        """
        for bound in range(min_bound, max_bound + 1):
            self.reset()
            result = self.verify_state_machine(state_machine, bound, property_name)
            yield result
            
            # 如果已经找到违反，停止
            if result.has_violation():
                break
            
            # 如果超时或错误，停止
            if result.status in (VerificationStatus.TIMEOUT, VerificationStatus.ERROR):
                break
