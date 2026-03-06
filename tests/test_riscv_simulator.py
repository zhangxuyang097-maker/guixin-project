"""RISC-V 模拟器单元测试.

测试 RISC-V RV32I 模拟器的正确性。
"""

import pytest
from typing import Any

from simulation.riscv_simulator import RISCVSimulator, RV32IRegisters, DecodedInstruction, InstructionType
from simulation.memory import Memory, MemoryRegion, MemoryPermission
from simulation.pmp import PMPChecker, PMPConfig, PMPRegion, PMPAddressMode
from core.exceptions import MemoryAccessError


class TestRV32IRegisters:
    """RV32IRegisters 测试类."""
    
    def test_register_creation(self) -> None:
        """测试寄存器创建."""
        regs = RV32IRegisters()
        
        # 所有寄存器初始为 0
        for i in range(32):
            assert regs.read(i) == 0
    
    def test_register_write_read(self) -> None:
        """测试寄存器写入和读取."""
        regs = RV32IRegisters()
        
        regs.write(1, 0x12345678)
        assert regs.read(1) == 0x12345678
    
    def test_x0_always_zero(self) -> None:
        """测试 x0 始终为 0."""
        regs = RV32IRegisters()
        
        regs.write(0, 0xFFFFFFFF)
        assert regs.read(0) == 0
    
    def test_register_names(self) -> None:
        """测试寄存器名称."""
        regs = RV32IRegisters()
        
        assert regs.get_name(0) == "zero"
        assert regs.get_name(1) == "ra"
        assert regs.get_name(2) == "sp"
        assert regs.get_name(10) == "a0"
    
    def test_register_reset(self) -> None:
        """测试寄存器重置."""
        regs = RV32IRegisters()
        
        regs.write(1, 0x12345678)
        regs.write(2, 0x87654321)
        
        regs.reset()
        
        assert regs.read(1) == 0
        assert regs.read(2) == 0


class TestMemory:
    """Memory 测试类."""
    
    def test_memory_creation(self) -> None:
        """测试内存创建."""
        mem = Memory(size=0x1000)
        
        assert mem.size == 0x1000
    
    def test_memory_region(self) -> None:
        """测试内存区域."""
        region = MemoryRegion(
            name="test",
            base_address=0x1000,
            size=0x1000,
            permission=MemoryPermission.READ_WRITE
        )
        
        assert region.name == "test"
        assert region.contains(0x1000) is True
        assert region.contains(0x1FFF) is True
        assert region.contains(0x2000) is False
    
    def test_add_memory_region(self) -> None:
        """测试添加内存区域."""
        mem = Memory(size=0x10000)
        
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x8000,
            permission=MemoryPermission.READ_WRITE
        )
        
        mem.add_region(region)
        
        assert mem.get_region(0x1000) == region
    
    def test_read_write_byte(self) -> None:
        """测试字节读写."""
        mem = Memory(size=0x1000)
        
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.READ_WRITE
        )
        mem.add_region(region)
        
        mem.write_byte(0x100, 0xAB)
        assert mem.read_byte(0x100) == 0xAB
    
    def test_read_write_word(self) -> None:
        """测试字读写."""
        mem = Memory(size=0x1000)
        
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.READ_WRITE
        )
        mem.add_region(region)
        
        mem.write_word(0x100, 0x12345678)
        assert mem.read_word(0x100) == 0x12345678
    
    def test_unaligned_access(self) -> None:
        """测试未对齐访问."""
        mem = Memory(size=0x1000)
        
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.READ_WRITE
        )
        mem.add_region(region)
        
        with pytest.raises(MemoryAccessError):
            mem.read_word(0x101)  # 未对齐地址
    
    def test_permission_violation(self) -> None:
        """测试权限违反."""
        mem = Memory(size=0x1000)
        
        region = MemoryRegion(
            name="ROM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.READ  # 只读
        )
        mem.add_region(region)
        
        with pytest.raises(MemoryAccessError):
            mem.write_byte(0x100, 0xAB)


class TestPMP:
    """PMP 测试类."""
    
    def test_pmp_region_creation(self) -> None:
        """测试 PMP 区域创建."""
        region = PMPRegion(
            index=0,
            base_address=0x1000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=True,
            execute_enabled=False
        )
        
        assert region.index == 0
        assert region.allows_read() is True
        assert region.allows_write() is True
        assert region.allows_execute() is False
    
    def test_pmp_config(self) -> None:
        """测试 PMP 配置."""
        config = PMPConfig()
        
        region = PMPRegion(
            index=0,
            base_address=0x1000,
            size=0x1000,
            read_enabled=True
        )
        
        config.add_region(region)
        
        assert len(config.regions) == 1
        assert config.get_region(0) == region
    
    def test_pmp_checker(self) -> None:
        """测试 PMP 检查器."""
        config = PMPConfig()
        
        region = PMPRegion(
            index=0,
            base_address=0x1000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=False
        )
        
        config.add_region(region)
        checker = PMPChecker(config)
        
        # 允许读
        allowed, error = checker.check_read(0x1000)
        assert allowed is True
        
        # 不允许写
        allowed, error = checker.check_write(0x1000)
        assert allowed is False
    
    def test_pmp_assert_access(self) -> None:
        """测试 PMP 断言访问."""
        config = PMPConfig()
        
        region = PMPRegion(
            index=0,
            base_address=0x1000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True
        )
        
        config.add_region(region)
        checker = PMPChecker(config)
        
        # 应该成功
        checker.assert_access(0x1000, 'read')
        
        # 应该抛出异常
        with pytest.raises(MemoryAccessError):
            checker.assert_access(0x3000, 'read')  # 不在任何区域内


class TestRISCVSimulator:
    """RISCVSimulator 测试类."""
    
    def test_simulator_creation(self) -> None:
        """测试模拟器创建."""
        sim = RISCVSimulator()
        
        assert sim.pc == 0
        assert sim.instruction_count == 0
    
    def test_reset(self) -> None:
        """测试重置."""
        sim = RISCVSimulator()
        
        sim.set_pc(0x1000)
        sim.registers.write(1, 0x12345678)
        
        sim.reset()
        
        assert sim.pc == 0
        assert sim.registers.read(1) == 0
    
    def test_decode_lui(self) -> None:
        """测试 LUI 指令解码."""
        sim = RISCVSimulator()
        
        # LUI x1, 0x12345
        instruction = 0x123450B7
        decoded = sim.decode_instruction(instruction)
        
        assert decoded.opcode == 0x37
        assert decoded.rd == 1
        assert decoded.imm == 0x12345000
        assert decoded.instr_type == InstructionType.U_TYPE
    
    def test_decode_addi(self) -> None:
        """测试 ADDI 指令解码."""
        sim = RISCVSimulator()
        
        # ADDI x1, x0, 10
        instruction = 0x00A00093
        decoded = sim.decode_instruction(instruction)
        
        assert decoded.opcode == 0x13
        assert decoded.rd == 1
        assert decoded.rs1 == 0
        assert decoded.funct3 == 0
        assert decoded.imm == 10
    
    def test_execute_lui(self) -> None:
        """测试 LUI 指令执行."""
        from simulation.pmp import PMPConfig, PMPRegion, PMPAddressMode
        sim = RISCVSimulator()
        
        # 创建内存区域
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.ALL
        )
        sim.memory.add_region(region)
        
        # 配置 PMP 区域（允许执行）
        pmp_config = PMPConfig()
        pmp_region = PMPRegion(
            index=0,
            base_address=0x0000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=True,
            execute_enabled=True
        )
        pmp_config.add_region(pmp_region)
        sim.pmp_checker = PMPChecker(pmp_config)
        
        # 加载 LUI 指令
        # LUI x1, 0x12345
        sim.memory.write_word(0, 0x123450B7)
        
        # 执行
        sim.step()
        
        assert sim.registers.read(1) == 0x12345000
        assert sim.pc == 4
    
    def test_execute_addi(self) -> None:
        """测试 ADDI 指令执行."""
        from simulation.pmp import PMPConfig, PMPRegion, PMPAddressMode
        sim = RISCVSimulator()
        
        # 创建内存区域
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.ALL
        )
        sim.memory.add_region(region)
        
        # 配置 PMP 区域（允许执行）
        pmp_config = PMPConfig()
        pmp_region = PMPRegion(
            index=0,
            base_address=0x0000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=True,
            execute_enabled=True
        )
        pmp_config.add_region(pmp_region)
        sim.pmp_checker = PMPChecker(pmp_config)
        
        # 加载 ADDI 指令
        # ADDI x1, x0, 10
        sim.memory.write_word(0, 0x00A00093)
        
        # 执行
        sim.step()
        
        assert sim.registers.read(1) == 10
    
    def test_execute_add(self) -> None:
        """测试 ADD 指令执行."""
        from simulation.pmp import PMPConfig, PMPRegion, PMPAddressMode
        sim = RISCVSimulator()
        
        # 创建内存区域
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.ALL
        )
        sim.memory.add_region(region)
        
        # 配置 PMP 区域（允许执行）
        pmp_config = PMPConfig()
        pmp_region = PMPRegion(
            index=0,
            base_address=0x0000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=True,
            execute_enabled=True
        )
        pmp_config.add_region(pmp_region)
        sim.pmp_checker = PMPChecker(pmp_config)
        
        # 设置寄存器值
        sim.registers.write(1, 10)
        sim.registers.write(2, 20)
        
        # 加载 ADD 指令
        # ADD x3, x1, x2
        sim.memory.write_word(0, 0x002081B3)
        
        # 执行
        sim.step()
        
        assert sim.registers.read(3) == 30
    
    def test_execute_lw_sw(self) -> None:
        """测试 LW/SW 指令执行."""
        from simulation.pmp import PMPConfig, PMPRegion, PMPAddressMode
        sim = RISCVSimulator()
        
        # 创建内存区域
        region = MemoryRegion(
            name="RAM",
            base_address=0x0000,
            size=0x1000,
            permission=MemoryPermission.ALL
        )
        sim.memory.add_region(region)
        
        # 配置 PMP 区域（允许执行）
        pmp_config = PMPConfig()
        pmp_region = PMPRegion(
            index=0,
            base_address=0x0000,
            size=0x1000,
            address_mode=PMPAddressMode.NAPOT,
            read_enabled=True,
            write_enabled=True,
            execute_enabled=True
        )
        pmp_config.add_region(pmp_region)
        sim.pmp_checker = PMPChecker(pmp_config)
        
        # 设置基地址寄存器
        sim.registers.write(1, 0x100)
        
        # 加载 SW 指令: SW x2, 0(x1)
        sim.memory.write_word(0, 0x0020A023)
        
        # 设置要存储的值
        sim.registers.write(2, 0x12345678)
        
        # 执行 SW
        sim.step()
        
        # 验证存储
        assert sim.memory.read_word(0x100) == 0x12345678
        
        # 重置 PC
        sim.set_pc(4)
        
        # 加载 LW 指令: LW x3, 0(x1)
        sim.memory.write_word(4, 0x0000A183)
        
        # 执行 LW
        sim.step()
        
        # 验证加载
        assert sim.registers.read(3) == 0x12345678


class TestInstructionEncoding:
    """指令编码测试类."""
    
    def test_r_type_encoding(self) -> None:
        """测试 R-type 指令编码."""
        # ADD x1, x2, x3
        # funct7=0, rs2=3, rs1=2, funct3=0, rd=1, opcode=0x33
        instruction = (0 << 25) | (3 << 20) | (2 << 15) | (0 << 12) | (1 << 7) | 0x33
        
        sim = RISCVSimulator()
        decoded = sim.decode_instruction(instruction)
        
        assert decoded.opcode == 0x33
        assert decoded.rd == 1
        assert decoded.rs1 == 2
        assert decoded.rs2 == 3
        assert decoded.funct3 == 0
        assert decoded.funct7 == 0
    
    def test_i_type_encoding(self) -> None:
        """测试 I-type 指令编码."""
        # ADDI x1, x2, 10
        # imm=10, rs1=2, funct3=0, rd=1, opcode=0x13
        instruction = (10 << 20) | (2 << 15) | (0 << 12) | (1 << 7) | 0x13
        
        sim = RISCVSimulator()
        decoded = sim.decode_instruction(instruction)
        
        assert decoded.opcode == 0x13
        assert decoded.rd == 1
        assert decoded.rs1 == 2
        assert decoded.imm == 10
