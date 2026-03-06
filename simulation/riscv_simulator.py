"""RISC-V RV32I 指令集模拟器模块.

实现 RISC-V RV32I 基础整数指令集的模拟器，
支持协议在 RISC-V 架构下的形式化验证和仿真测试。

特性：
- 完整的 RV32I 指令集支持
- 寄存器文件管理
- 内存访问（带 PMP 检查）
- 异常处理
- 执行统计
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum, auto
import struct

from core.exceptions import SimulationError, MemoryAccessError
from simulation.memory import Memory, MemoryRegion, MemoryPermission
from simulation.pmp import PMPChecker, PMPConfig


class RV32IRegisters:
    """RV32I 寄存器文件.
    
    管理 32 个 32 位通用寄存器（x0-x31）。
    x0 始终为 0，写入被忽略。
    
    Attributes:
        _regs: 寄存器数组
    """
    
    # 寄存器名称映射
    REG_NAMES = {
        0: "zero", 1: "ra", 2: "sp", 3: "gp",
        4: "tp", 5: "t0", 6: "t1", 7: "t2",
        8: "s0", 9: "s1", 10: "a0", 11: "a1",
        12: "a2", 13: "a3", 14: "a4", 15: "a5",
        16: "a6", 17: "a7", 18: "s2", 19: "s3",
        20: "s4", 21: "s5", 22: "s6", 23: "s7",
        24: "s8", 25: "s9", 26: "s10", 27: "s11",
        28: "t3", 29: "t4", 30: "t5", 31: "t6",
    }
    
    def __init__(self) -> None:
        """初始化寄存器文件."""
        self._regs: list[int] = [0] * 32
    
    def read(self, reg_num: int) -> int:
        """读取寄存器值.
        
        Args:
            reg_num: 寄存器编号（0-31）
            
        Returns:
            32 位寄存器值
            
        Raises:
            AssertionError: 如果寄存器编号无效
        """
        assert 0 <= reg_num <= 31, f"寄存器编号 {reg_num} 超出范围"
        return self._regs[reg_num]
    
    def write(self, reg_num: int, value: int) -> None:
        """写入寄存器值.
        
        Args:
            reg_num: 寄存器编号（0-31）
            value: 32 位值
            
        Raises:
            AssertionError: 如果寄存器编号无效
        """
        assert 0 <= reg_num <= 31, f"寄存器编号 {reg_num} 超出范围"
        # x0 始终为 0
        if reg_num != 0:
            self._regs[reg_num] = value & 0xFFFFFFFF
    
    def get_name(self, reg_num: int) -> str:
        """获取寄存器名称.
        
        Args:
            reg_num: 寄存器编号
            
        Returns:
            寄存器名称
        """
        return self.REG_NAMES.get(reg_num, f"x{reg_num}")
    
    def reset(self) -> None:
        """重置所有寄存器为 0."""
        self._regs = [0] * 32
    
    def dump(self) -> dict[str, int]:
        """转储所有寄存器值.
        
        Returns:
            寄存器名称到值的字典
        """
        return {
            self.get_name(i): self._regs[i]
            for i in range(32)
        }


class InstructionType(Enum):
    """指令类型枚举."""
    
    R_TYPE = auto()  # 寄存器类型
    I_TYPE = auto()  # 立即数类型
    S_TYPE = auto()  # 存储类型
    B_TYPE = auto()  # 分支类型
    U_TYPE = auto()  # 上位立即数类型
    J_TYPE = auto()  # 跳转类型


@dataclass
class DecodedInstruction:
    """解码后的指令.
    
    Attributes:
        opcode: 操作码
        rd: 目标寄存器
        rs1: 源寄存器 1
        rs2: 源寄存器 2
        funct3: 功能码 3
        funct7: 功能码 7
        imm: 立即数
        instr_type: 指令类型
    """
    
    opcode: int
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    funct3: int = 0
    funct7: int = 0
    imm: int = 0
    instr_type: InstructionType = InstructionType.R_TYPE


class RISCVSimulator:
    """RISC-V RV32I 模拟器.
    
    实现 RISC-V RV32I 指令集的完整模拟器。
    
    Attributes:
        memory: 内存实例
        registers: 寄存器文件
        pc: 程序计数器
        pmp_checker: PMP 检查器
        instruction_count: 执行指令计数
        cycle_count: 时钟周期计数
        _running: 是否正在运行
        _breakpoints: 断点集合
        _trace_enabled: 是否启用追踪
    """
    
    # 操作码定义
    OPCODE_LUI = 0x37
    OPCODE_AUIPC = 0x17
    OPCODE_JAL = 0x6F
    OPCODE_JALR = 0x67
    OPCODE_BRANCH = 0x63
    OPCODE_LOAD = 0x03
    OPCODE_STORE = 0x23
    OPCODE_OP_IMM = 0x13
    OPCODE_OP = 0x33
    OPCODE_MISC_MEM = 0x0F
    OPCODE_SYSTEM = 0x73
    
    def __init__(
        self,
        memory: Optional[Memory] = None,
        pmp_config: Optional[PMPConfig] = None
    ) -> None:
        """初始化 RISC-V 模拟器.
        
        Args:
            memory: 内存实例，创建默认内存如果未提供
            pmp_config: PMP 配置
        """
        self.memory = memory or Memory(0x10000)  # 默认 64KB
        self.registers = RV32IRegisters()
        self.pc: int = 0
        self.pmp_checker = PMPChecker(pmp_config)
        self.instruction_count: int = 0
        self.cycle_count: int = 0
        self._running: bool = False
        self._breakpoints: set[int] = set()
        self._trace_enabled: bool = False
        self._trace_handler: Optional[Callable[[str], None]] = None
        self._exception_handler: Optional[Callable[[Exception], None]] = None
    
    def reset(self) -> None:
        """重置模拟器状态."""
        self.registers.reset()
        self.pc = 0
        self.instruction_count = 0
        self.cycle_count = 0
        self._running = False
    
    def load_program(self, program: bytes, address: int = 0) -> None:
        """加载程序到内存.
        
        Args:
            program: 程序字节码
            address: 加载地址
            
        Raises:
            MemoryAccessError: 如果加载失败
        """
        self.memory.load_program(address, program)
    
    def set_pc(self, address: int) -> None:
        """设置程序计数器.
        
        Args:
            address: 新 PC 值
        """
        assert address % 4 == 0, "PC 必须 4 字节对齐"
        self.pc = address
    
    def fetch_instruction(self) -> int:
        """取指令.
        
        Returns:
            32 位指令
            
        Raises:
            MemoryAccessError: 如果取指失败
        """
        # PMP 检查
        self.pmp_checker.assert_access(self.pc, 'execute')
        
        return self.memory.read_word(self.pc)
    
    def decode_instruction(self, instruction: int) -> DecodedInstruction:
        """解码指令.
        
        Args:
            instruction: 32 位指令
            
        Returns:
            解码后的指令
        """
        opcode = instruction & 0x7F
        
        decoded = DecodedInstruction(opcode=opcode)
        
        if opcode == self.OPCODE_LUI or opcode == self.OPCODE_AUIPC:
            # U-type
            decoded.rd = (instruction >> 7) & 0x1F
            decoded.imm = instruction & 0xFFFFF000
            decoded.instr_type = InstructionType.U_TYPE
            
        elif opcode == self.OPCODE_JAL:
            # J-type
            decoded.rd = (instruction >> 7) & 0x1F
            imm_20 = (instruction >> 31) & 0x1
            imm_10_1 = (instruction >> 21) & 0x3FF
            imm_11 = (instruction >> 20) & 0x1
            imm_19_12 = (instruction >> 12) & 0xFF
            decoded.imm = (imm_20 << 20) | (imm_19_12 << 12) | (imm_11 << 11) | (imm_10_1 << 1)
            if decoded.imm & 0x100000:  # 符号扩展
                decoded.imm |= 0xFFE00000
            decoded.instr_type = InstructionType.J_TYPE
            
        elif opcode == self.OPCODE_JALR:
            # I-type
            decoded.rd = (instruction >> 7) & 0x1F
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.imm = (instruction >> 20) & 0xFFF
            if decoded.imm & 0x800:  # 符号扩展
                decoded.imm |= 0xFFFFF000
            decoded.instr_type = InstructionType.I_TYPE
            
        elif opcode == self.OPCODE_BRANCH:
            # B-type
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.rs2 = (instruction >> 20) & 0x1F
            imm_12 = (instruction >> 31) & 0x1
            imm_10_5 = (instruction >> 25) & 0x3F
            imm_4_1 = (instruction >> 8) & 0xF
            imm_11 = (instruction >> 7) & 0x1
            decoded.imm = (imm_12 << 12) | (imm_11 << 11) | (imm_10_5 << 5) | (imm_4_1 << 1)
            if decoded.imm & 0x1000:  # 符号扩展
                decoded.imm |= 0xFFFFE000
            decoded.instr_type = InstructionType.B_TYPE
            
        elif opcode == self.OPCODE_LOAD:
            # I-type
            decoded.rd = (instruction >> 7) & 0x1F
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.imm = (instruction >> 20) & 0xFFF
            if decoded.imm & 0x800:  # 符号扩展
                decoded.imm |= 0xFFFFF000
            decoded.instr_type = InstructionType.I_TYPE
            
        elif opcode == self.OPCODE_STORE:
            # S-type
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.rs2 = (instruction >> 20) & 0x1F
            imm_11_5 = (instruction >> 25) & 0x7F
            imm_4_0 = (instruction >> 7) & 0x1F
            decoded.imm = (imm_11_5 << 5) | imm_4_0
            if decoded.imm & 0x800:  # 符号扩展
                decoded.imm |= 0xFFFFF000
            decoded.instr_type = InstructionType.S_TYPE
            
        elif opcode == self.OPCODE_OP_IMM:
            # I-type
            decoded.rd = (instruction >> 7) & 0x1F
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.imm = (instruction >> 20) & 0xFFF
            if decoded.imm & 0x800:  # 符号扩展
                decoded.imm |= 0xFFFFF000
            decoded.funct7 = (instruction >> 25) & 0x7F
            decoded.instr_type = InstructionType.I_TYPE
            
        elif opcode == self.OPCODE_OP:
            # R-type
            decoded.rd = (instruction >> 7) & 0x1F
            decoded.funct3 = (instruction >> 12) & 0x7
            decoded.rs1 = (instruction >> 15) & 0x1F
            decoded.rs2 = (instruction >> 20) & 0x1F
            decoded.funct7 = (instruction >> 25) & 0x7F
            decoded.instr_type = InstructionType.R_TYPE
        
        return decoded
    
    def execute_instruction(self, decoded: DecodedInstruction) -> None:
        """执行解码后的指令.
        
        Args:
            decoded: 解码后的指令
            
        Raises:
            SimulationError: 如果执行失败
        """
        opcode = decoded.opcode
        
        if opcode == self.OPCODE_LUI:
            # LUI
            self.registers.write(decoded.rd, decoded.imm)
            self.pc += 4
            
        elif opcode == self.OPCODE_AUIPC:
            # AUIPC
            result = (self.pc + decoded.imm) & 0xFFFFFFFF
            self.registers.write(decoded.rd, result)
            self.pc += 4
            
        elif opcode == self.OPCODE_JAL:
            # JAL
            self.registers.write(decoded.rd, self.pc + 4)
            self.pc = (self.pc + decoded.imm) & 0xFFFFFFFF
            
        elif opcode == self.OPCODE_JALR:
            # JALR
            rs1_val = self.registers.read(decoded.rs1)
            self.registers.write(decoded.rd, self.pc + 4)
            self.pc = ((rs1_val + decoded.imm) & 0xFFFFFFFE)
            
        elif opcode == self.OPCODE_BRANCH:
            # Branch instructions
            rs1_val = self.registers.read(decoded.rs1)
            rs2_val = self.registers.read(decoded.rs2)
            
            # 符号扩展
            if rs1_val & 0x80000000:
                rs1_val |= 0xFFFFFFFF00000000
            if rs2_val & 0x80000000:
                rs2_val |= 0xFFFFFFFF00000000
            
            branch_taken = False
            
            if decoded.funct3 == 0x0:  # BEQ
                branch_taken = rs1_val == rs2_val
            elif decoded.funct3 == 0x1:  # BNE
                branch_taken = rs1_val != rs2_val
            elif decoded.funct3 == 0x4:  # BLT
                branch_taken = rs1_val < rs2_val
            elif decoded.funct3 == 0x5:  # BGE
                branch_taken = rs1_val >= rs2_val
            elif decoded.funct3 == 0x6:  # BLTU
                branch_taken = (rs1_val & 0xFFFFFFFF) < (rs2_val & 0xFFFFFFFF)
            elif decoded.funct3 == 0x7:  # BGEU
                branch_taken = (rs1_val & 0xFFFFFFFF) >= (rs2_val & 0xFFFFFFFF)
            
            if branch_taken:
                self.pc = (self.pc + decoded.imm) & 0xFFFFFFFF
            else:
                self.pc += 4
                
        elif opcode == self.OPCODE_LOAD:
            # Load instructions
            rs1_val = self.registers.read(decoded.rs1)
            address = (rs1_val + decoded.imm) & 0xFFFFFFFF
            
            # PMP 检查
            self.pmp_checker.assert_access(address, 'read')
            
            if decoded.funct3 == 0x0:  # LB
                value = self.memory.read_byte(address)
                if value & 0x80:  # 符号扩展
                    value |= 0xFFFFFF00
                self.registers.write(decoded.rd, value)
            elif decoded.funct3 == 0x1:  # LH
                value = self.memory.read_halfword(address)
                if value & 0x8000:  # 符号扩展
                    value |= 0xFFFF0000
                self.registers.write(decoded.rd, value)
            elif decoded.funct3 == 0x2:  # LW
                value = self.memory.read_word(address)
                self.registers.write(decoded.rd, value)
            elif decoded.funct3 == 0x4:  # LBU
                value = self.memory.read_byte(address)
                self.registers.write(decoded.rd, value)
            elif decoded.funct3 == 0x5:  # LHU
                value = self.memory.read_halfword(address)
                self.registers.write(decoded.rd, value)
            
            self.pc += 4
            
        elif opcode == self.OPCODE_STORE:
            # Store instructions
            rs1_val = self.registers.read(decoded.rs1)
            rs2_val = self.registers.read(decoded.rs2)
            address = (rs1_val + decoded.imm) & 0xFFFFFFFF
            
            # PMP 检查
            self.pmp_checker.assert_access(address, 'write')
            
            if decoded.funct3 == 0x0:  # SB
                self.memory.write_byte(address, rs2_val)
            elif decoded.funct3 == 0x1:  # SH
                self.memory.write_halfword(address, rs2_val)
            elif decoded.funct3 == 0x2:  # SW
                self.memory.write_word(address, rs2_val)
            
            self.pc += 4
            
        elif opcode == self.OPCODE_OP_IMM:
            # OP-IMM instructions
            rs1_val = self.registers.read(decoded.rs1)
            imm = decoded.imm
            
            # 符号扩展 rs1_val
            if rs1_val & 0x80000000:
                rs1_val_signed = rs1_val | 0xFFFFFFFF00000000
            else:
                rs1_val_signed = rs1_val
            
            if decoded.funct3 == 0x0:  # ADDI
                result = (rs1_val_signed + imm) & 0xFFFFFFFF
            elif decoded.funct3 == 0x2:  # SLTI
                result = 1 if rs1_val_signed < imm else 0
            elif decoded.funct3 == 0x3:  # SLTIU
                result = 1 if rs1_val < (imm & 0xFFFFFFFF) else 0
            elif decoded.funct3 == 0x4:  # XORI
                result = rs1_val ^ (imm & 0xFFFFFFFF)
            elif decoded.funct3 == 0x6:  # ORI
                result = rs1_val | (imm & 0xFFFFFFFF)
            elif decoded.funct3 == 0x7:  # ANDI
                result = rs1_val & (imm & 0xFFFFFFFF)
            elif decoded.funct3 == 0x1:  # SLLI
                shamt = imm & 0x1F
                result = (rs1_val << shamt) & 0xFFFFFFFF
            elif decoded.funct3 == 0x5:
                if (imm >> 5) & 0x7F == 0x00:  # SRLI
                    shamt = imm & 0x1F
                    result = (rs1_val >> shamt) & 0xFFFFFFFF
                else:  # SRAI
                    shamt = imm & 0x1F
                    if rs1_val & 0x80000000:
                        result = (rs1_val >> shamt) | (0xFFFFFFFF << (32 - shamt))
                    else:
                        result = rs1_val >> shamt
                    result &= 0xFFFFFFFF
            else:
                raise SimulationError(f"未知的 OP-IMM funct3: {decoded.funct3}", self.pc)
            
            self.registers.write(decoded.rd, result)
            self.pc += 4
            
        elif opcode == self.OPCODE_OP:
            # OP instructions
            rs1_val = self.registers.read(decoded.rs1)
            rs2_val = self.registers.read(decoded.rs2)
            
            # 符号扩展
            if rs1_val & 0x80000000:
                rs1_val_signed = rs1_val | 0xFFFFFFFF00000000
            else:
                rs1_val_signed = rs1_val
            if rs2_val & 0x80000000:
                rs2_val_signed = rs2_val | 0xFFFFFFFF00000000
            else:
                rs2_val_signed = rs2_val
            
            if decoded.funct3 == 0x0:
                if decoded.funct7 == 0x00:  # ADD
                    result = (rs1_val_signed + rs2_val_signed) & 0xFFFFFFFF
                elif decoded.funct7 == 0x20:  # SUB
                    result = (rs1_val_signed - rs2_val_signed) & 0xFFFFFFFF
                else:
                    raise SimulationError(f"未知的 ADD/SUB funct7: {decoded.funct7}", self.pc)
            elif decoded.funct3 == 0x1:  # SLL
                shamt = rs2_val & 0x1F
                result = (rs1_val << shamt) & 0xFFFFFFFF
            elif decoded.funct3 == 0x2:  # SLT
                result = 1 if rs1_val_signed < rs2_val_signed else 0
            elif decoded.funct3 == 0x3:  # SLTU
                result = 1 if rs1_val < rs2_val else 0
            elif decoded.funct3 == 0x4:  # XOR
                result = rs1_val ^ rs2_val
            elif decoded.funct3 == 0x5:
                shamt = rs2_val & 0x1F
                if decoded.funct7 == 0x00:  # SRL
                    result = (rs1_val >> shamt) & 0xFFFFFFFF
                elif decoded.funct7 == 0x20:  # SRA
                    if rs1_val & 0x80000000:
                        result = (rs1_val >> shamt) | (0xFFFFFFFF << (32 - shamt))
                    else:
                        result = rs1_val >> shamt
                    result &= 0xFFFFFFFF
                else:
                    raise SimulationError(f"未知的 SRL/SRA funct7: {decoded.funct7}", self.pc)
            elif decoded.funct3 == 0x6:  # OR
                result = rs1_val | rs2_val
            elif decoded.funct3 == 0x7:  # AND
                result = rs1_val & rs2_val
            else:
                raise SimulationError(f"未知的 OP funct3: {decoded.funct3}", self.pc)
            
            self.registers.write(decoded.rd, result)
            self.pc += 4
        else:
            raise SimulationError(f"未知的操作码: {opcode:#x}", self.pc)
    
    def step(self) -> bool:
        """执行单条指令.
        
        Returns:
            是否成功执行
            
        Raises:
            SimulationError: 如果执行失败
            MemoryAccessError: 如果内存访问失败
        """
        # 检查断点（仅在运行模式下）
        if self._running and self.pc in self._breakpoints:
            self._running = False
            return False
        
        try:
            # 取指
            instruction = self.fetch_instruction()
            
            # 解码
            decoded = self.decode_instruction(instruction)
            
            # 追踪
            if self._trace_enabled and self._trace_handler:
                self._trace_handler(f"PC={self.pc:08x}: {instruction:08x}")
            
            # 执行
            self.execute_instruction(decoded)
            
            # 更新计数
            self.instruction_count += 1
            self.cycle_count += 1
            
            return True
            
        except Exception as e:
            if self._exception_handler:
                self._exception_handler(e)
            raise
    
    def run(self, max_instructions: Optional[int] = None) -> int:
        """运行程序.
        
        Args:
            max_instructions: 最大执行指令数（无限制如果为 None）
            
        Returns:
            执行的指令数
        """
        self._running = True
        count = 0
        
        while self._running:
            if max_instructions is not None and count >= max_instructions:
                break
            
            try:
                if not self.step():
                    break
                count += 1
            except Exception:
                self._running = False
                raise
        
        return count
    
    def stop(self) -> None:
        """停止运行."""
        self._running = False
    
    def add_breakpoint(self, address: int) -> None:
        """添加断点.
        
        Args:
            address: 断点地址
        """
        self._breakpoints.add(address)
    
    def remove_breakpoint(self, address: int) -> None:
        """移除断点.
        
        Args:
            address: 断点地址
        """
        self._breakpoints.discard(address)
    
    def enable_trace(self, handler: Optional[Callable[[str], None]] = None) -> None:
        """启用指令追踪.
        
        Args:
            handler: 追踪处理函数
        """
        self._trace_enabled = True
        self._trace_handler = handler
    
    def disable_trace(self) -> None:
        """禁用指令追踪."""
        self._trace_enabled = False
        self._trace_handler = None
    
    def set_exception_handler(self, handler: Callable[[Exception], None]) -> None:
        """设置异常处理器.
        
        Args:
            handler: 异常处理函数
        """
        self._exception_handler = handler
    
    def get_statistics(self) -> dict[str, Any]:
        """获取执行统计信息.
        
        Returns:
            统计信息字典
        """
        return {
            "instruction_count": self.instruction_count,
            "cycle_count": self.cycle_count,
            "pc": self.pc,
            "running": self._running,
            "breakpoints": len(self._breakpoints),
        }
