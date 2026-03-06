# 轨芯安 (RailCore Secure) 用户使用手册

> **面向国产 RISC-V 架构的轨道交通信号安全协议形式化验证工具**

---

## 目录

1. [项目概述](#1-项目概述)
2. [安装指南](#2-安装指南)
3. [快速开始](#3-快速开始)
4. [核心模块详解](#4-核心模块详解)
5. [GUI 使用指南](#5-gui-使用指南)
6. [命令行使用](#6-命令行使用)
7. [验证场景说明](#7-验证场景说明)
8. [API 参考](#8-api-参考)
9. [故障排除](#9-故障排除)
10. [最佳实践](#10-最佳实践)

---

## 1. 项目概述

### 1.1 什么是轨芯安

**轨芯安 (RailCore Secure)** 是一款专为轨道交通信号系统设计的轻量级形式化验证工具，支持 RSSP-I/II 安全通信协议在国产 RISC-V 架构下的验证，满足 **SIL4 级安全完整性要求**。

### 1.2 核心特性

| 特性 | 描述 | 状态 |
|------|------|------|
| 形式化验证引擎 | 基于 Z3 SMT 求解器的有界模型检测 (BMC) | 已实现 |
| 协议支持 | 完整实现 RSSP-I 和 RSSP-II 协议状态机 | 已实现 |
| RISC-V 模拟 | RV32I 指令集模拟器，支持 PMP 权限检查 | 已实现 |
| 可视化界面 | PyQt6 实现的图形用户界面 | 已实现 |
| 并发仿真 | 基于 Asyncio 的多节点协议仿真 | 已实现 |
| 故障注入 | 支持重放攻击、序列号错误等多种故障场景 | 已实现 |

### 1.3 技术栈

- **Python 3.9+**: 主要开发语言
- **Z3 Solver**: 形式化验证引擎
- **PyQt6**: GUI 框架
- **Pydantic**: 数据校验
- **Asyncio**: 并发仿真
- **Pytest**: 单元测试

---

## 2. 安装指南

### 2.1 系统要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+), macOS, Windows 10/11
- **Python**: 3.9 或更高版本
- **内存**: 至少 4GB RAM
- **磁盘空间**: 至少 500MB 可用空间

### 2.2 安装步骤

#### 2.2.1 克隆仓库

```bash
git clone https://github.com/zhangxuyang097-maker/guixin-project.git
cd railcore-secure
```

#### 2.2.2 创建虚拟环境

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

#### 2.2.3 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `z3-solver>=4.12.0` - Z3 SMT 求解器
- `pydantic>=2.0.0` - 数据验证
- `PyQt6>=6.5.0` - GUI 框架
- `pytest>=7.4.0` - 测试框架

#### 2.2.4 验证安装

```bash
# 运行测试套件
pytest tests/ -v

# 预期输出: 104 passed
```

### 2.3 开发模式安装

```bash
pip install -e ".[dev]"
```

这将安装额外的开发依赖：
- 代码格式化工具 (Black, isort)
- 类型检查工具 (mypy)
- 代码质量工具 (flake8)

---

## 3. 快速开始

### 3.1 启动 GUI

```bash
python -m gui.main_window
```

或使用快捷命令：
```bash
railcore-gui
```

### 3.2 运行第一个验证

```python
from core.verification_engine import BMCEngine
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from core.verification_scenarios import VerificationScenarios

# 创建协议实例
config = RSSPIConfig(node_id=1)
protocol = RSSPIProtocol(config)

# 创建验证场景
scenario = VerificationScenarios.create_normal_operation_scenario("RSSP-I")

# 运行验证
context = scenario.setup_func()
result = scenario.run_func(context)

print(f"验证结果: {result.status.name}")
print(f"消息: {result.message}")
```

### 3.3 运行所有验证场景

```python
from core.verification_scenarios import ScenarioRunner

# 创建场景运行器
runner = ScenarioRunner()

# 运行 RSSP-I 的所有场景
results = runner.run_all_scenarios("RSSP-I")

# 获取摘要
summary = runner.get_summary()
print(f"总场景数: {summary['total_scenarios']}")
print(f"通过: {summary['passed']}")
print(f"失败: {summary['failed']}")
print(f"通过率: {summary['pass_rate']*100:.1f}%")
```

---

## 4. 核心模块详解

### 4.1 异常处理模块 (`core/exceptions.py`)

轨芯安定义了完整的异常类体系，便于上层捕获和处理。

#### 4.1.1 异常类层次

```
RailCoreError (基类)
├── VerificationError      # 形式化验证错误
├── ProtocolViolationError # 协议违反错误
├── SimulationError        # 仿真执行错误
│   └── MemoryAccessError  # 内存访问错误
├── TimeoutError           # 超时错误
└── ConfigurationError     # 配置错误
```

#### 4.1.2 错误严重级别

```python
from core.exceptions import ErrorSeverity

severity = ErrorSeverity.WARNING   # 警告
severity = ErrorSeverity.ERROR     # 错误
severity = ErrorSeverity.CRITICAL  # 严重
severity = ErrorSeverity.FATAL     # 致命
```

#### 4.1.3 使用示例

```python
from core.exceptions import ProtocolViolationError, ErrorSeverity

try:
    # 协议操作
    protocol.receive_message(message)
except ProtocolViolationError as e:
    print(f"错误代码: {e.error_code}")
    print(f"严重级别: {e.severity.value}")
    print(f"消息: {e.message}")
    print(f"上下文: {e.context}")
```

### 4.2 状态机模块 (`core/state_machine.py`)

#### 4.2.1 创建自定义状态机

```python
from core.state_machine import StateMachine, State, StateType, Transition

# 创建状态机
sm = StateMachine()

# 添加状态
sm.add_state(State("IDLE", StateType.INITIAL))
sm.add_state(State("RUNNING", StateType.NORMAL))
sm.add_state(State("ERROR", StateType.FINAL))

# 添加转移
sm.add_transition(Transition("IDLE", "RUNNING", event="start"))
sm.add_transition(Transition("RUNNING", "ERROR", event="fail"))
sm.add_transition(Transition("ERROR", "IDLE", event="reset"))

# 执行状态转移
sm.step({}, "start")  # IDLE -> RUNNING
```

#### 4.2.2 状态类型

| 类型 | 说明 |
|------|------|
| `INITIAL` | 初始状态，状态机启动时的默认状态 |
| `NORMAL` | 普通状态，正常执行的状态 |
| `FINAL` | 终止状态，状态机可以在此状态结束 |

### 4.3 BMC 验证引擎 (`core/verification_engine.py`)

#### 4.3.1 基本使用

```python
from core.verification_engine import BMCEngine, Property, VerificationStatus
from protocol.rssp_i import RSSPIProtocol

# 创建 BMC 引擎
engine = BMCEngine(timeout_ms=30000)

# 定义属性
def check_safety(ctx):
    return ctx.current_state != "ERROR"

prop = Property(
    name="no_error_state",
    description="状态机不能进入错误状态",
    predicate=check_safety,
    property_type="safety"
)

# 添加属性
engine.add_property(prop)

# 创建协议实例
protocol = RSSPIProtocol()

# 执行验证
result = engine.verify_state_machine(protocol, bound=10)

# 处理结果
if result.status == VerificationStatus.VERIFIED:
    print("验证通过！")
elif result.status == VerificationStatus.VIOLATION_FOUND:
    print(f"发现违反: {result.counter_example}")
```

#### 4.3.2 增量验证

```python
# 从边界 1 开始，逐步增加到 100
for result in engine.verify_incremental(protocol, min_bound=1, max_bound=100):
    print(f"边界 {result.bound}: {result.status.name}")
    if result.has_violation():
        print(f"最小反例在边界 {result.bound}")
        break
```

#### 4.3.3 验证结果

```python
result = engine.verify_state_machine(protocol, bound=10)

# 结果属性
print(f"状态: {result.status.name}")           # VERIFIED, VIOLATION_FOUND, TIMEOUT, ERROR, UNKNOWN
print(f"属性: {result.property_name}")
print(f"边界: {result.bound}")
print(f"耗时: {result.time_seconds:.3f} 秒")
print(f"消息: {result.message}")

# 反例信息（如果有）
if result.counter_example:
    print(f"违反步数: {result.counter_example.step}")
    print(f"违反状态: {result.counter_example.state}")
    print(f"变量值: {result.counter_example.variable_values}")
    print(f"执行轨迹: {result.counter_example.trace}")

# 求解器统计
print(f"总检查次数: {result.solver_stats.get('total_checks')}")
print(f"SAT 结果: {result.solver_stats.get('sat_results')}")
print(f"UNSAT 结果: {result.solver_stats.get('unsat_results')}")
```

### 4.4 RSSP-I 协议 (`protocol/rssp_i.py`)

#### 4.4.1 协议配置

```python
from protocol.rssp_i import RSSPIConfig

config = RSSPIConfig(
    max_sequence_number=0xFFFFFFFF,  # 最大序列号
    window_size=1024,                 # 接收窗口大小
    timeout_ms=1000,                  # 超时时间（毫秒）
    max_retransmissions=3,            # 最大重传次数
    heartbeat_interval_ms=5000,       # 心跳间隔（毫秒）
    node_id=1                         # 本节点 ID
)
```

#### 4.4.2 协议状态

```
CLOSED (初始)
    │
    ├── active_open ──> SYN_SENT
    │
    └── passive_open ──> LISTEN

SYN_SENT
    │
    ├── recv_syn ──> SYN_RECEIVED
    │
    └── recv_synack ──> ESTABLISHED

LISTEN
    │
    └── recv_syn ──> SYN_RECEIVED

SYN_RECEIVED
    │
    └── recv_ack ──> ESTABLISHED

ESTABLISHED
    │
    └── active_close ──> FIN_WAIT
```

#### 4.4.3 基本操作

```python
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig
from protocol.message import RSSPMessage, MessageType

# 创建协议实例
config = RSSPIConfig(node_id=1)
protocol = RSSPIProtocol(config)

# 主动建立连接
protocol.connect(peer_id=2)

# 发送数据
message = protocol.send_data(b"Hello, World!")
print(f"发送消息，序列号: {message.sequence_number}")

# 接收消息
incoming_msg = RSSPMessage(
    msg_type=MessageType.DATA,
    sequence_number=0,
    payload=b"Response",
    source_id=2,
    dest_id=1
)
incoming_msg.update_checksum()
protocol.receive_message(incoming_msg)

# 检查超时并重传
timeout_msgs = protocol.check_timeouts()
for msg in timeout_msgs:
    print(f"需要重传: {msg.sequence_number}")

# 关闭连接
protocol.close()

# 获取统计信息
stats = protocol.get_statistics()
print(f"当前状态: {stats['current_state']}")
print(f"下一序列号: {stats['next_sequence_number']}")
print(f"发送缓冲区大小: {stats['send_buffer_size']}")
```

#### 4.4.4 消息处理回调

```python
# 设置消息发送处理器
def on_message_send(message: RSSPMessage):
    print(f"发送消息: {message.msg_type.name}")
    # 实际发送消息到网络

protocol.set_message_handler(on_message_send)

# 设置错误处理器
def on_error(error: Exception):
    print(f"协议错误: {error}")

protocol.set_error_handler(on_error)
```

### 4.5 RSSP-II 协议 (`protocol/rssp_ii.py`)

#### 4.5.1 协议配置

```python
from protocol.rssp_ii import RSSPIIConfig

config = RSSPIIConfig(
    max_sequence_number=0xFFFFFFFF,
    window_size=1024,
    timeout_ms=1000,
    max_retransmissions=3,
    heartbeat_interval_ms=5000,
    node_id=1,
    dual_channel=True,                    # 启用双通道
    safety_code_key=b"secret_key_32bytes", # 安全码密钥
    safety_code_validity_ms=5000          # 安全码有效期
)
```

#### 4.5.2 双通道支持

```python
from protocol.rssp_ii import RSSPIIProtocol, RSSPIIConfig

# 创建双通道协议实例
config = RSSPIIConfig(node_id=1, dual_channel=True)
protocol = RSSPIIProtocol(config)

# 启动协议
protocol.start()

# 建立连接
protocol.establish_connection(peer_id=2)

# 发送安全数据（生成主通道和备用通道消息）
primary, secondary = protocol.send_safe_data(b"Critical data")

# 检查双通道状态
if protocol.dual_channel_state.is_operational():
    print("至少一个通道可用")

# 模拟通道故障
protocol.dual_channel_state.set_channel_state('A', False)
print(f"通道 A 状态: {protocol.dual_channel_state.get_channel_state('A')}")
print(f"通道 B 状态: {protocol.dual_channel_state.get_channel_state('B')}")
```

### 4.6 消息模块 (`protocol/message.py`)

#### 4.6.1 创建消息

```python
from protocol.message import RSSPMessage, MessageType

# 创建数据消息
msg = RSSPMessage(
    msg_type=MessageType.DATA,
    sequence_number=1,
    timestamp=1234567890,
    payload=b"Hello",
    source_id=1,
    dest_id=2
)

# 更新校验和
msg.update_checksum()

# 验证校验和
if msg.verify_checksum():
    print("校验和正确")
```

#### 4.6.2 消息类型

| 类型 | 说明 |
|------|------|
| `DATA` | 数据消息 |
| `ACK` | 确认消息 |
| `SYNC` | 同步消息（连接建立） |
| `FIN` | 结束消息（连接关闭） |
| `HEARTBEAT` | 心跳消息 |

#### 4.6.3 序列化和反序列化

```python
# 序列化
serialized = msg.serialize()
print(f"序列化后长度: {len(serialized)} 字节")

# 反序列化
restored_msg = RSSPMessage.deserialize(serialized)
print(f"恢复的消息类型: {restored_msg.msg_type.name}")
```

### 4.7 RISC-V 模拟器 (`simulation/riscv_simulator.py`)

#### 4.7.1 基本使用

```python
from simulation.riscv_simulator import RISCVSimulator, RISCVConfig
from simulation.memory import MemoryRegion

# 创建配置
config = RISCVConfig(
    memory_size=65536,
    enable_pmp=True,
    pmp_regions=8
)

# 创建模拟器
sim = RISCVSimulator(config)

# 加载程序
program = bytes([
    0x93, 0x00, 0x00, 0x00,  # addi x1, x0, 0
    0x13, 0x01, 0x10, 0x00,  # addi x2, x0, 1
])
sim.load_program(program)

# 运行程序
sim.run()

# 获取状态
state = sim.get_state()
print(f"PC: 0x{state['pc']:08x}")
print(f"执行指令数: {state['instruction_count']}")
print(f"寄存器 x1: 0x{state['registers'][1]:08x}")
```

#### 4.7.2 单步执行

```python
# 重置模拟器
sim.reset()

# 单步执行
while True:
    success = sim.step()
    if not success:
        break
    
    state = sim.get_state()
    print(f"PC: 0x{state['pc']:08x}")
```

#### 4.7.3 断点调试

```python
# 添加断点
sim.add_breakpoint(0x100)
sim.add_breakpoint(0x200)

# 运行到断点
sim.run()  # 会在第一个断点处停止

# 继续执行
sim.resume()

# 移除断点
sim.remove_breakpoint(0x100)

# 清除所有断点
sim.clear_breakpoints()
```

### 4.8 PMP 权限检查 (`simulation/pmp.py`)

#### 4.8.1 配置 PMP 区域

```python
from simulation.pmp import PMPConfig, PMPAddressMode, PMPRegion

# 创建 PMP 配置
pmp_config = PMPConfig(num_regions=8)

# 配置代码区域 (只读执行)
pmp_config.configure_region(
    region_index=0,
    start_addr=0x0000,
    end_addr=0x7FFF,
    read=True,
    write=False,
    execute=True,
    address_mode=PMPAddressMode.NAPOT
)

# 配置数据区域 (读写)
pmp_config.configure_region(
    region_index=1,
    start_addr=0x8000,
    end_addr=0xFFFF,
    read=True,
    write=True,
    execute=False,
    address_mode=PMPAddressMode.NAPOT
)
```

#### 4.8.2 权限检查

```python
from simulation.pmp import PMPChecker

# 创建检查器
checker = PMPChecker(pmp_config)

# 检查读权限
allowed, error = checker.check_access(
    address=0x1000,
    access_type="read",
    is_machine_mode=False
)
if allowed:
    print("读访问允许")
else:
    print(f"读访问拒绝: {error}")

# 检查写权限
allowed, error = checker.check_access(
    address=0x1000,
    access_type="write",
    is_machine_mode=False
)
```

---

## 5. GUI 使用指南

### 5.1 启动 GUI

```bash
python -m gui.main_window
```

### 5.2 界面布局

GUI 界面分为三个主要区域：

1. **左侧面板** - 控制区
   - 协议选择
   - 验证场景选择
   - 参数设置
   - 控制按钮

2. **右侧面板** - 结果展示区
   - 验证结果标签页
   - 运行日志标签页
   - 统计信息标签页

3. **顶部工具栏**
   - 运行按钮
   - 清空按钮

### 5.3 执行验证

1. **选择协议**
   - 从"协议选择"下拉框选择 RSSP-I 或 RSSP-II

2. **选择场景**
   - 正常操作
   - 重放攻击
   - 序列号错误
   - 校验和错误
   - 双通道故障（仅 RSSP-II）

3. **设置参数**
   - 验证边界：控制 BMC 展开的最大步数（默认 10）

4. **运行验证**
   - 点击"运行验证"按钮
   - 观察进度条和日志输出
   - 查看验证结果

### 5.4 结果解读

**验证状态说明：**

| 状态 | 含义 |
|------|------|
| `VERIFIED` | 验证通过，所有属性满足 |
| `VIOLATION_FOUND` | 发现属性违反，存在反例 |
| `TIMEOUT` | 验证超时 |
| `ERROR` | 验证过程出错 |
| `UNKNOWN` | 求解器返回未知结果 |

**反例信息：**
- 步数：属性违反发生的步数
- 状态：违反时的状态机状态
- 变量值：相关变量的赋值
- 执行轨迹：导致违反的状态序列

---

## 6. 命令行使用

### 6.1 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_rssp_protocols.py -v

# 运行特定测试函数
pytest tests/test_rssp_protocols.py::test_rssp_i_normal_operation -v

# 生成覆盖率报告
pytest --cov=. --cov-report=html
pytest --cov=. --cov-report=xml
```

### 6.2 代码质量检查

```bash
# 代码格式化
black .

# 导入排序
isort .

# 类型检查
mypy .

# 代码风格检查
flake8
```

### 6.3 性能分析

```bash
# 行级性能分析
kernprof -l -v script.py

# 内存分析
python -m memory_profiler script.py
```

---

## 7. 验证场景说明

### 7.1 场景类型

| 场景 | 类型 | 描述 | 适用协议 |
|------|------|------|----------|
| 正常操作 | NORMAL_OPERATION | 建立连接并发送数据 | RSSP-I/II |
| 重放攻击 | REPLAY_ATTACK | 验证协议能否检测重放消息 | RSSP-I/II |
| 序列号错误 | SEQUENCE_ERROR | 验证协议能否检测乱序消息 | RSSP-I/II |
| 校验和错误 | CHECKSUM_ERROR | 验证协议能否检测数据篡改 | RSSP-I/II |
| 双通道故障 | DUAL_CHANNEL_FAULT | 验证单通道故障时系统仍能工作 | RSSP-II |

### 7.2 创建自定义场景

```python
from core.verification_scenarios import (
    VerificationScenario, ScenarioType, VerificationScenarios
)
from core.verification_engine import VerificationResult, VerificationStatus

def create_custom_scenario():
    def setup():
        # 初始化协议实例
        protocol = RSSPIProtocol(RSSPIConfig(node_id=1))
        return protocol
    
    def run(protocol):
        # 执行验证逻辑
        # ...
        
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            property_name="custom_property",
            bound=10,
            time_seconds=0.1,
            message="自定义场景验证通过"
        )
    
    return VerificationScenario(
        name="custom_scenario",
        description="自定义验证场景",
        scenario_type=ScenarioType.FAULT_INJECTION,
        protocol_type="RSSP-I",
        setup_func=setup,
        run_func=run,
        expected_result=VerificationStatus.VERIFIED
    )

# 运行自定义场景
scenario = create_custom_scenario()
runner = ScenarioRunner()
result = runner.run_scenario(scenario)
```

### 7.3 属性规约

#### 7.3.1 预定义属性

```python
from core.verification_scenarios import ProtocolProperties

# 序列号单调性
prop1 = ProtocolProperties.create_sequence_monotonicity_property()

# 防重放
prop2 = ProtocolProperties.create_no_replay_property()

# 窗口不变式
prop3 = ProtocolProperties.create_window_invariant_property(max_window_size=1024)

# 校验和有效性
prop4 = ProtocolProperties.create_checksum_validity_property()

# 双通道一致性（RSSP-II）
prop5 = ProtocolProperties.create_dual_channel_consistency_property()

# 安全码有效性（RSSP-II）
prop6 = ProtocolProperties.create_safety_code_validity_property()
```

#### 7.3.2 自定义属性

```python
from core.verification_engine import Property

def check_custom_property(ctx):
    """自定义属性检查函数."""
    # 检查逻辑
    return ctx.some_value > 0

prop = Property(
    name="custom_property",
    description="自定义安全属性",
    predicate=check_custom_property,
    property_type="safety"
)

# 添加到 BMC 引擎
engine.add_property(prop)
```

---

## 8. API 参考

### 8.1 BMCEngine

```python
class BMCEngine:
    def __init__(self, timeout_ms: int = 30000)
    def add_property(self, prop: Property) -> None
    def reset(self) -> None
    def verify_state_machine(self, state_machine: StateMachine, 
                             bound: int = 10,
                             property_name: Optional[str] = None) -> VerificationResult
    def verify_incremental(self, state_machine: StateMachine,
                          min_bound: int = 1,
                          max_bound: int = 100,
                          property_name: Optional[str] = None) -> Generator[VerificationResult, None, None]
    def get_statistics(self) -> dict[str, Any]
```

### 8.2 RSSPIProtocol

```python
class RSSPIProtocol(StateMachine):
    def __init__(self, config: Optional[RSSPIConfig] = None)
    def initialize(self) -> None
    def connect(self, peer_id: int) -> None
    def close(self) -> None
    def send_data(self, payload: bytes) -> RSSPMessage
    def receive_message(self, message: RSSPMessage) -> None
    def check_timeouts(self) -> list[RSSPMessage]
    def set_message_handler(self, handler: Callable[[RSSPMessage], None]) -> None
    def set_error_handler(self, handler: Callable[[Exception], None]) -> None
    def get_statistics(self) -> dict[str, Any]
```

### 8.3 RSSPIIProtocol

```python
class RSSPIIProtocol(StateMachine):
    def __init__(self, config: Optional[RSSPIIConfig] = None)
    def initialize(self) -> None
    def start(self) -> None
    def establish_connection(self, peer_id: int) -> None
    def send_safe_data(self, payload: bytes) -> tuple[RSSPMessage, Optional[RSSPMessage]]
    def receive_message(self, message: RSSPMessage, channel: str = 'A') -> None
    def get_statistics(self) -> dict[str, Any]
```

### 8.4 RISCVSimulator

```python
class RISCVSimulator:
    def __init__(self, config: Optional[RISCVConfig] = None)
    def load_program(self, program: bytes, address: int = 0) -> None
    def run(self) -> bool
    def step(self) -> bool
    def reset(self) -> None
    def resume(self) -> bool
    def pause(self) -> None
    def add_breakpoint(self, address: int) -> None
    def remove_breakpoint(self, address: int) -> None
    def clear_breakpoints(self) -> None
    def get_state(self) -> dict[str, Any]
```

---

## 9. 故障排除

### 9.1 常见问题

#### 问题 1: Z3 求解器安装失败

**症状：**
```
ERROR: Could not find a version that satisfies the requirement z3-solver
```

**解决方案：**
```bash
# 更新 pip
pip install --upgrade pip

# 手动安装 Z3
pip install z3-solver==4.12.0

# 或使用系统包管理器
# Ubuntu/Debian
sudo apt-get install python3-z3

# macOS
brew install z3
```

#### 问题 2: PyQt6 安装失败

**症状：**
```
ERROR: Failed building wheel for PyQt6
```

**解决方案：**
```bash
# 安装 Qt 开发依赖
# Ubuntu/Debian
sudo apt-get install qt6-base-dev

# 或使用预编译包
pip install PyQt6 --only-binary :all:
```

#### 问题 3: 测试失败

**症状：**
```
FAILED tests/test_rssp_protocols.py::test_rssp_i_normal_operation
```

**解决方案：**
```bash
# 详细输出
pytest tests/test_rssp_protocols.py -v --tb=short

# 调试模式
pytest tests/test_rssp_protocols.py -v --pdb

# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

#### 问题 4: GUI 无法启动

**症状：**
```
qt.qpa.plugin: Could not load the Qt platform plugin
```

**解决方案：**
```bash
# 设置平台插件路径
export QT_QPA_PLATFORM_PLUGIN_PATH=/path/to/plugins

# 或使用 X11 平台
export QT_QPA_PLATFORM=xcb

# 无头模式测试
export QT_QPA_PLATFORM=offscreen
```

### 9.2 调试技巧

#### 启用详细日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("railcore")
logger.setLevel(logging.DEBUG)
```

#### 检查状态机状态

```python
# 获取当前状态
current = protocol.get_current_state()
print(f"当前状态: {current.name if current else 'None'}")

# 获取所有状态
for name, state in protocol._states.items():
    print(f"状态: {name}, 类型: {state.state_type.name}")

# 获取所有转移
for trans in protocol._transitions:
    print(f"转移: {trans.source} -> {trans.target}, 事件: {trans.event}")
```

#### 验证引擎调试

```python
# 获取统计信息
stats = engine.get_statistics()
print(f"总检查次数: {stats['total_checks']}")
print(f"SAT 结果: {stats['sat_results']}")
print(f"UNSAT 结果: {stats['unsat_results']}")
print(f"总耗时: {stats['total_time_ms']:.2f} ms")
```

### 9.3 性能优化

#### 减少验证边界

```python
# 如果验证太慢，减少边界
result = engine.verify_state_machine(protocol, bound=5)  # 而不是 10
```

#### 使用增量验证

```python
# 找到最小反例
for result in engine.verify_incremental(protocol, min_bound=1, max_bound=50):
    if result.has_violation():
        print(f"最小反例在边界 {result.bound}")
        break
```

#### 并行执行场景

```python
import asyncio
from core.simulation_engine import SimulationEngine

async def run_parallel():
    engine = SimulationEngine()
    
    # 添加多个节点
    engine.add_node(1, RSSPIProtocol(RSSPIConfig(node_id=1)))
    engine.add_node(2, RSSPIProtocol(RSSPIConfig(node_id=2)))
    
    # 并行运行
    await engine.run_simulation(duration_seconds=10)

asyncio.run(run_parallel())
```

---

## 10. 最佳实践

### 10.1 代码组织

```
my_verification/
├── __init__.py
├── config.py          # 配置定义
├── scenarios.py       # 自定义场景
├── properties.py      # 自定义属性
└── main.py            # 入口脚本
```

### 10.2 配置管理

```python
# config.py
from protocol.rssp_i import RSSPIConfig
from protocol.rssp_ii import RSSPIIConfig

# 开发环境配置
DEV_CONFIG = RSSPIConfig(
    node_id=1,
    timeout_ms=500,
    window_size=256
)

# 生产环境配置
PROD_CONFIG = RSSPIConfig(
    node_id=1,
    timeout_ms=1000,
    window_size=1024,
    max_retransmissions=5
)

# 测试环境配置
TEST_CONFIG = RSSPIConfig(
    node_id=1,
    timeout_ms=100,
    window_size=64,
    max_retransmissions=2
)
```

### 10.3 错误处理

```python
from core.exceptions import (
    RailCoreError, ProtocolViolationError, 
    VerificationError, TimeoutError
)

def safe_verify(protocol, engine):
    try:
        result = engine.verify_state_machine(protocol, bound=10)
        return result
    except ProtocolViolationError as e:
        logger.error(f"协议违反: {e.message}")
        # 记录到监控系统
        metrics.record_protocol_violation(e)
    except VerificationError as e:
        logger.error(f"验证错误: {e.message}")
        # 可能需要调整验证参数
        raise
    except TimeoutError as e:
        logger.warning(f"验证超时: {e.operation}")
        # 增加超时时间重试
        engine.timeout_ms *= 2
        return engine.verify_state_machine(protocol, bound=10)
    except RailCoreError as e:
        logger.error(f"轨芯安错误 [{e.error_code}]: {e.message}")
        raise
```

### 10.4 测试策略

```python
# 单元测试示例
import pytest
from protocol.rssp_i import RSSPIProtocol, RSSPIConfig

class TestRSSPIProtocol:
    def setup_method(self):
        self.config = RSSPIConfig(node_id=1)
        self.protocol = RSSPIProtocol(self.config)
    
    def test_initial_state(self):
        assert self.protocol.get_current_state().name == "CLOSED"
    
    def test_connect(self):
        self.protocol.connect(2)
        assert self.protocol.get_current_state().name == "SYN_SENT"
    
    def test_send_data_in_wrong_state(self):
        with pytest.raises(ProtocolViolationError):
            self.protocol.send_data(b"test")
```

### 10.5 文档规范

```python
def my_function(param1: int, param2: str) -> bool:
    """简短描述.
    
    详细描述，可以包含多行。
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回值的描述
        
    Raises:
        ProtocolViolationError: 当协议被违反时
        VerificationError: 当验证失败时
        
    Example:
        >>> result = my_function(1, "test")
        >>> print(result)
        True
    """
    pass
```

---

## 附录

### A. 术语表

| 术语 | 说明 |
|------|------|
| BMC | 有界模型检测 (Bounded Model Checking) |
| RSSP | 轨道交通信号安全协议 (Railway Signal Safety Protocol) |
| PMP | 物理内存保护 (Physical Memory Protection) |
| SIL4 | 安全完整性等级 4 (Safety Integrity Level 4) |
| SMT | 可满足性模理论 (Satisfiability Modulo Theories) |
| Z3 | Microsoft Research 开发的 SMT 求解器 |

### B. 参考资料

- [EN 50128:2011](https://www.cenelec.eu/) - 铁路应用：通信、信号和处理系统
- [IEC 61508](https://webstore.iec.ch/) - 电气/电子/可编程电子安全相关系统的功能安全
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
- [Z3 API Documentation](https://z3prover.github.io/api/html/z3.html)

### C. 获取帮助

- **项目主页**: https://github.com/zhangxuyang097-maker/guixin-project
- **问题反馈**: https://github.com/zhangxuyang097-maker/guixin-project/issues
- **邮箱**: 1262599687@qq.com

---

**轨芯安 - 守护轨道交通安全**

*本文档版本: 2.0.0 | 最后更新: 2026-03-06*
