# 轨芯安 (RailCore Secure)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> 面向国产 RISC-V 架构的轨道交通信号安全协议轻量化形式化验证工具

## 项目简介

轨芯安是一款专为轨道交通信号系统设计的轻量级形式化验证工具，支持 RSSP-I/II 安全通信协议在国产 RISC-V 架构下的验证，满足 SIL4 级安全完整性要求。

### 核心特性

- **形式化验证引擎**: 基于 Z3 SMT 求解器的有界模型检测 (BMC)
- **协议支持**: 完整实现 RSSP-I 和 RSSP-II 协议状态机
- **RISC-V 模拟**: RV32I 指令集模拟器，支持 PMP 权限检查
- **可视化界面**: PyQt6 实现的图形用户界面
- **并发仿真**: 基于 Asyncio 的多节点协议仿真
- **故障注入**: 支持重放攻击、序列号错误等多种故障场景
- **基准测试**: 完整的基准测试套件，支持专业测试报告输出

## 技术栈

- **Python 3.9+**: 主要开发语言
- **Z3 Solver**: 形式化验证引擎
- **PyQt6**: GUI 框架
- **Pydantic**: 数据校验
- **Asyncio**: 并发仿真
- **Pytest**: 单元测试

## 快速开始

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/zhangxuyang097-maker/guixin-project.git
cd railcore-secure

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行 GUI

```bash
python -m gui.main_window
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_rssp_protocols.py -v

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

### 运行基准测试

```bash
# 运行完整基准测试套件
python run_benchmark.py

# 或使用模块方式
python -m core.benchmark
```

### 命令行使用

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

## 项目结构

```
railcore_secure/
├── core/                      # 核心验证引擎
│   ├── exceptions.py          # 异常定义
│   ├── state_machine.py       # 状态机基类
│   ├── verification_engine.py # BMC 引擎
│   ├── verification_scenarios.py # 验证场景
│   ├── simulation_engine.py   # 并发仿真引擎
│   └── benchmark.py           # 基准测试模块
├── protocol/                  # 协议模型
│   ├── message.py             # 消息格式
│   ├── rssp_i.py              # RSSP-I 协议
│   └── rssp_ii.py             # RSSP-II 协议
├── simulation/                # 仿真模块
│   ├── memory.py              # 内存模拟
│   ├── pmp.py                 # PMP 权限检查
│   └── riscv_simulator.py     # RISC-V 模拟器
├── gui/                       # 图形界面
│   ├── main_window.py         # 主窗口
│   ├── verification_widget.py # 验证部件
│   └── simulation_widget.py   # 仿真部件
├── tests/                     # 单元测试
│   ├── test_exceptions.py
│   ├── test_state_machine.py
│   ├── test_rssp_protocols.py
│   ├── test_riscv_simulator.py
│   └── test_verification_scenarios.py
├── 第一次使用请看这个/          # 文档
│   ├── SIL4_SAFETY_MANUAL.md  # SIL4 安全手册
│   ├── USER_GUIDE.md          # 用户使用手册
│   └── 项目总结_创新大赛.md    # 项目总结
├── requirements.txt           # 依赖项
├── pytest.ini                 # Pytest 配置
├── run_benchmark.py           # 基准测试入口
└── README.md                  # 本文件
```

## 验证场景

### RSSP-I 协议验证

| 场景 | 描述 | 状态 |
|------|------|------|
| 正常操作 | 建立连接并发送数据 | 通过 |
| 重放攻击 | 检测重复消息 | 通过 |
| 序列号错误 | 检测乱序消息 | 通过 |
| 校验和错误 | 检测数据篡改 | 通过 |

### RSSP-II 协议验证

| 场景 | 描述 | 状态 |
|------|------|------|
| 正常操作 | 安全数据传输 | 通过 |
| 重放攻击 | 检测重放消息 | 通过 |
| 双通道故障 | 单通道容错 | 通过 |
| 安全码验证 | 消息认证 | 通过 |

## 基准测试

### 测试套件

| 套件 | 测试数 | 描述 |
|------|--------|------|
| 基础轨道状态机测试 | 8 | 状态机核心功能测试 |
| 经典协议基准测试 (RSSP-I) | 8 | RSSP-I 协议功能测试 |
| RSSP-II 轨道协议测试 | 9 | RSSP-II 协议功能测试 |
| RISC-V 指令安全测试 | 11 | RISC-V 模拟器测试 |

### 运行基准测试

```bash
python run_benchmark.py
```

输出示例：
```
======================================================================
  轨芯安 (RailCore Secure) 基准测试套件
======================================================================

  【测试汇总】
  │ 总测试项: 36
  │ 通过: 36
  │ 通过率: 100.0%

  【最终结论】
  │  工具状态: ✓ 合格
  │  评估结果: 满足 SIL4 级安全要求
======================================================================
```

## 安全属性

### 已验证属性

- **序列号单调性**: 序列号必须单调递增
- **防重放**: 不允许重复消息
- **窗口不变式**: 接收窗口大小限制
- **校验和有效性**: 数据完整性验证
- **双通道一致性**: 至少一个通道活跃
- **安全码有效性**: 消息认证和时效性

## RISC-V 支持

### 指令集

- **RV32I**: 完整支持基础整数指令集
- **PMP**: 支持物理内存保护

### 内存区域

| 区域 | 地址范围 | 权限 |
|------|----------|------|
| 代码区 | 0x0000 - 0x7FFF | R-X |
| 数据区 | 0x8000 - 0xFFFF | RW- |

## SIL4 认证

本项目按照 EN 50128:2011 标准设计，满足 SIL4 级安全要求：

- 完整的软件生命周期文档
- 形式化验证方法应用
- 全面的测试覆盖（>90%）
- 故障注入和容错测试
- 基准测试套件验证

详见 [SIL4 安全手册](第一次使用请看这个/SIL4_SAFETY_MANUAL.md)

## 开发规范

### 代码风格

- **类型安全**: 所有函数使用 Type Hints
- **文档规范**: Google Style Docstring
- **代码格式化**: Black
- **导入排序**: isort

### 测试要求

- 单元测试覆盖率 > 90%
- 所有安全属性必须测试
- 故障注入路径必须覆盖
- 基准测试全部通过

## 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目主页: https://github.com/zhangxuyang097-maker/guixin-project
- 问题反馈: https://github.com/zhangxuyang097-maker/guixin-project/issues
- 邮箱: 1262599687@qq.com

## 致谢

- Microsoft Research Z3 团队
- RISC-V 基金会
- 轨道交通信号安全社区

---

**轨芯安 - 守护轨道交通安全**
