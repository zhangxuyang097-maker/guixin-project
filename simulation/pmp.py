"""PMP (Physical Memory Protection) 模块.

实现 RISC-V PMP 权限检查机制，支持内存访问权限控制。
PMP 用于确保关键代码和数据不被未授权访问，是 SIL4 安全的关键组件。
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum, auto

from core.exceptions import MemoryAccessError


class PMPAddressMode(Enum):
    """PMP 地址匹配模式枚举."""
    
    OFF = 0
    TOR = 1  # Top of Range
    NA4 = 2  # Naturally aligned 4-byte region
    NAPOT = 3  # Naturally aligned power-of-two region


@dataclass
class PMPRegion:
    """PMP 区域定义.
    
    定义一个 PMP 保护区域的配置。
    
    Attributes:
        index: 区域索引（0-15）
        base_address: 基地址
        size: 区域大小（字节）
        address_mode: 地址匹配模式
        read_enabled: 是否允许读
        write_enabled: 是否允许写
        execute_enabled: 是否允许执行
        locked: 是否锁定（需要复位才能修改）
    """
    
    index: int
    base_address: int = 0
    size: int = 0
    address_mode: PMPAddressMode = PMPAddressMode.OFF
    read_enabled: bool = False
    write_enabled: bool = False
    execute_enabled: bool = False
    locked: bool = False
    
    def __post_init__(self) -> None:
        """验证 PMP 区域参数."""
        assert 0 <= self.index <= 15, "PMP 区域索引必须在 0-15 范围内"
        assert self.base_address >= 0, "基地址不能为负"
        assert self.size >= 0, "大小不能为负"
    
    def matches(self, address: int) -> bool:
        """检查地址是否匹配此区域.
        
        Args:
            address: 要检查的地址
            
        Returns:
            是否匹配
        """
        if self.address_mode == PMPAddressMode.OFF:
            return False
        
        if self.address_mode == PMPAddressMode.TOR:
            # TOR 模式：匹配 [prev_region.base, self.base)
            # 这里简化处理，实际应使用前一个区域的基地址
            return address < self.base_address
        
        if self.address_mode == PMPAddressMode.NA4:
            return (address >= self.base_address and 
                    address < self.base_address + 4)
        
        if self.address_mode == PMPAddressMode.NAPOT:
            # NAPOT 模式：基地址的低几位编码大小
            # 简化实现
            return (address >= self.base_address and 
                    address < self.base_address + self.size)
        
        return False
    
    def allows_read(self) -> bool:
        """检查是否允许读访问."""
        return self.read_enabled
    
    def allows_write(self) -> bool:
        """检查是否允许写访问."""
        return self.write_enabled
    
    def allows_execute(self) -> bool:
        """检查是否允许执行访问."""
        return self.execute_enabled
    
    def to_config_byte(self) -> int:
        """转换为配置字节.
        
        Returns:
            PMP 配置字节值
        """
        config = 0
        if self.read_enabled:
            config |= 0x01
        if self.write_enabled:
            config |= 0x02
        if self.execute_enabled:
            config |= 0x04
        if self.locked:
            config |= 0x80
        config |= (self.address_mode.value & 0x03) << 3
        return config
    
    @classmethod
    def from_config_byte(cls, index: int, config: int, address: int) -> "PMPRegion":
        """从配置字节创建 PMP 区域.
        
        Args:
            index: 区域索引
            config: 配置字节
            address: 地址寄存器值
            
        Returns:
            PMP 区域对象
        """
        read_enabled = bool(config & 0x01)
        write_enabled = bool(config & 0x02)
        execute_enabled = bool(config & 0x04)
        locked = bool(config & 0x80)
        address_mode = PMPAddressMode((config >> 3) & 0x03)
        
        # 计算大小（NAPOT 模式）
        size = 0
        if address_mode == PMPAddressMode.NA4:
            size = 4
        elif address_mode == PMPAddressMode.NAPOT:
            # 从地址的低几位计算大小
            trailing_ones = 0
            temp_addr = address
            while temp_addr & 0x01:
                trailing_ones += 1
                temp_addr >>= 1
            if trailing_ones > 0:
                size = 4 << trailing_ones
        
        return cls(
            index=index,
            base_address=address,
            size=size,
            address_mode=address_mode,
            read_enabled=read_enabled,
            write_enabled=write_enabled,
            execute_enabled=execute_enabled,
            locked=locked,
        )


@dataclass
class PMPConfig:
    """PMP 配置.
    
    管理所有 PMP 区域的配置。
    
    Attributes:
        regions: PMP 区域列表
        enabled: PMP 是否启用
    """
    
    regions: list[PMPRegion] = field(default_factory=list)
    enabled: bool = True
    
    def __post_init__(self) -> None:
        """初始化 PMP 配置."""
        # 确保最多 16 个区域
        if len(self.regions) > 16:
            self.regions = self.regions[:16]
    
    def add_region(self, region: PMPRegion) -> None:
        """添加 PMP 区域.
        
        Args:
            region: PMP 区域定义
            
        Raises:
            AssertionError: 如果区域索引已存在或超过限制
        """
        assert len(self.regions) < 16, "PMP 区域数量不能超过 16"
        
        for existing in self.regions:
            if existing.index == region.index:
                raise AssertionError(f"PMP 区域索引 {region.index} 已存在")
        
        self.regions.append(region)
        # 按索引排序
        self.regions.sort(key=lambda r: r.index)
    
    def get_region(self, index: int) -> Optional[PMPRegion]:
        """获取指定索引的 PMP 区域.
        
        Args:
            index: 区域索引
            
        Returns:
            PMP 区域对象，如果不存在则返回 None
        """
        for region in self.regions:
            if region.index == index:
                return region
        return None
    
    def update_region(self, index: int, region: PMPRegion) -> None:
        """更新 PMP 区域.
        
        Args:
            index: 区域索引
            region: 新的 PMP 区域定义
            
        Raises:
            AssertionError: 如果区域被锁定
        """
        existing = self.get_region(index)
        if existing is None:
            raise AssertionError(f"PMP 区域索引 {index} 不存在")
        
        if existing.locked:
            raise AssertionError(f"PMP 区域 {index} 已锁定，无法修改")
        
        # 替换区域
        for i, r in enumerate(self.regions):
            if r.index == index:
                self.regions[i] = region
                break
    
    def clear(self) -> None:
        """清空所有 PMP 区域."""
        # 只清除未锁定的区域
        self.regions = [r for r in self.regions if r.locked]


class PMPChecker:
    """PMP 权限检查器.
    
    执行 PMP 权限检查，确保内存访问符合 PMP 配置。
    
    Attributes:
        config: PMP 配置
    """
    
    def __init__(self, config: Optional[PMPConfig] = None) -> None:
        """初始化 PMP 检查器.
        
        Args:
            config: PMP 配置，使用默认配置如果未提供
        """
        self.config = config or PMPConfig()
    
    def check_access(
        self,
        address: int,
        access_type: str,
        is_machine_mode: bool = False
    ) -> tuple[bool, Optional[str]]:
        """检查内存访问权限.
        
        Args:
            address: 访问地址
            access_type: 访问类型 ('read', 'write', 'execute')
            is_machine_mode: 是否为机器模式
            
        Returns:
            (是否允许, 错误信息)
        """
        # 如果 PMP 未启用，允许所有访问
        if not self.config.enabled:
            return True, None
        
        # 机器模式下，如果没有配置任何 PMP 区域，允许所有访问
        if is_machine_mode and not self.config.regions:
            return True, None
        
        # 查找匹配的 PMP 区域（优先级：索引大的优先）
        matching_region = None
        for region in reversed(self.config.regions):
            if region.matches(address):
                matching_region = region
                break
        
        # 如果没有匹配的区域，拒绝访问（非机器模式）
        if matching_region is None:
            if is_machine_mode:
                return True, None
            return False, f"地址 {address:#x} 不在任何 PMP 区域内"
        
        # 检查权限
        if access_type == 'read':
            if not matching_region.allows_read():
                return False, f"地址 {address:#x} 没有读权限"
        elif access_type == 'write':
            if not matching_region.allows_write():
                return False, f"地址 {address:#x} 没有写权限"
        elif access_type == 'execute':
            if not matching_region.allows_execute():
                return False, f"地址 {address:#x} 没有执行权限"
        else:
            return False, f"未知的访问类型: {access_type}"
        
        return True, None
    
    def check_read(
        self,
        address: int,
        is_machine_mode: bool = False
    ) -> tuple[bool, Optional[str]]:
        """检查读访问权限.
        
        Args:
            address: 访问地址
            is_machine_mode: 是否为机器模式
            
        Returns:
            (是否允许, 错误信息)
        """
        return self.check_access(address, 'read', is_machine_mode)
    
    def check_write(
        self,
        address: int,
        is_machine_mode: bool = False
    ) -> tuple[bool, Optional[str]]:
        """检查写访问权限.
        
        Args:
            address: 访问地址
            is_machine_mode: 是否为机器模式
            
        Returns:
            (是否允许, 错误信息)
        """
        return self.check_access(address, 'write', is_machine_mode)
    
    def check_execute(
        self,
        address: int,
        is_machine_mode: bool = False
    ) -> tuple[bool, Optional[str]]:
        """检查执行权限.
        
        Args:
            address: 访问地址
            is_machine_mode: 是否为机器模式
            
        Returns:
            (是否允许, 错误信息)
        """
        return self.check_access(address, 'execute', is_machine_mode)
    
    def assert_access(
        self,
        address: int,
        access_type: str,
        is_machine_mode: bool = False
    ) -> None:
        """断言访问权限（失败时抛出异常）.
        
        Args:
            address: 访问地址
            access_type: 访问类型
            is_machine_mode: 是否为机器模式
            
        Raises:
            MemoryAccessError: 如果访问被拒绝
        """
        allowed, error_msg = self.check_access(address, access_type, is_machine_mode)
        if not allowed:
            raise MemoryAccessError(
                error_msg or "PMP 权限检查失败",
                address=address,
                access_type=access_type
            )
    
    def get_statistics(self) -> dict[str, Any]:
        """获取 PMP 统计信息.
        
        Returns:
            统计信息字典
        """
        return {
            "enabled": self.config.enabled,
            "region_count": len(self.config.regions),
            "locked_regions": sum(1 for r in self.config.regions if r.locked),
            "active_regions": sum(1 for r in self.config.regions 
                                if r.address_mode != PMPAddressMode.OFF),
        }
