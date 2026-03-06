"""内存模拟模块.

提供 RISC-V 模拟器所需的内存管理功能，
支持内存区域划分、访问权限控制和边界检查。
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum, auto

from core.exceptions import MemoryAccessError, SimulationError


class MemoryPermission(Enum):
    """内存权限枚举."""
    
    NONE = 0
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    READ_WRITE = auto()
    READ_EXECUTE = auto()
    ALL = auto()


@dataclass
class MemoryRegion:
    """内存区域定义.
    
    Attributes:
        name: 区域名称
        base_address: 基地址
        size: 区域大小（字节）
        permission: 访问权限
        initialized: 是否已初始化
    """
    
    name: str
    base_address: int
    size: int
    permission: MemoryPermission = MemoryPermission.READ_WRITE
    initialized: bool = False
    
    def __post_init__(self) -> None:
        """验证内存区域参数."""
        assert self.size > 0, "内存区域大小必须大于 0"
        assert self.base_address >= 0, "基地址不能为负"
        assert self.base_address + self.size <= 0xFFFFFFFF, "内存区域超出 32 位地址空间"
    
    def contains(self, address: int) -> bool:
        """检查地址是否在区域内.
        
        Args:
            address: 要检查的地址
            
        Returns:
            是否在区域内
        """
        return self.base_address <= address < self.base_address + self.size
    
    def offset(self, address: int) -> int:
        """计算地址在区域内的偏移.
        
        Args:
            address: 地址
            
        Returns:
            偏移量
        """
        return address - self.base_address
    
    def end_address(self) -> int:
        """获取区域结束地址.
        
        Returns:
            结束地址（不包含）
        """
        return self.base_address + self.size


class Memory:
    """内存模拟类.
    
    模拟 RISC-V 32 位地址空间，支持多区域管理和权限控制。
    
    Attributes:
        size: 内存大小
        _data: 内存数据
        _regions: 内存区域列表
    """
    
    def __init__(self, size: int = 0x100000) -> None:
        """初始化内存.
        
        Args:
            size: 内存大小（字节），默认 1MB
        """
        self.size = size
        self._data: bytearray = bytearray(size)
        self._regions: list[MemoryRegion] = []
    
    def add_region(self, region: MemoryRegion) -> None:
        """添加内存区域.
        
        Args:
            region: 内存区域定义
            
        Raises:
            AssertionError: 如果区域重叠或超出范围
        """
        # 检查区域是否超出内存范围
        if region.end_address() > self.size:
            raise AssertionError(f"区域 '{region.name}' 超出内存范围")
        
        # 检查区域是否重叠
        for existing in self._regions:
            if (region.base_address < existing.end_address() and
                region.end_address() > existing.base_address):
                raise AssertionError(
                    f"区域 '{region.name}' 与 '{existing.name}' 重叠"
                )
        
        self._regions.append(region)
        region.initialized = True
    
    def get_region(self, address: int) -> Optional[MemoryRegion]:
        """获取地址所属的内存区域.
        
        Args:
            address: 地址
            
        Returns:
            内存区域，如果不属于任何区域则返回 None
        """
        for region in self._regions:
            if region.contains(address):
                return region
        return None
    
    def read_byte(self, address: int) -> int:
        """读取单字节.
        
        Args:
            address: 地址
            
        Returns:
            字节值（0-255）
            
        Raises:
            MemoryAccessError: 如果访问无效
        """
        if address < 0 or address >= self.size:
            raise MemoryAccessError(
                f"地址 {address:#x} 超出内存范围",
                address=address,
                access_type="read"
            )
        
        region = self.get_region(address)
        if region is None:
            raise MemoryAccessError(
                f"地址 {address:#x} 不在任何内存区域内",
                address=address,
                access_type="read"
            )
        
        if region.permission in (MemoryPermission.NONE, 
                                  MemoryPermission.WRITE,
                                  MemoryPermission.EXECUTE):
            raise MemoryAccessError(
                f"地址 {address:#x} 没有读权限",
                address=address,
                access_type="read",
                pmp_region=id(region)
            )
        
        return self._data[address]
    
    def write_byte(self, address: int, value: int) -> None:
        """写入单字节.
        
        Args:
            address: 地址
            value: 字节值（0-255）
            
        Raises:
            MemoryAccessError: 如果访问无效
        """
        if address < 0 or address >= self.size:
            raise MemoryAccessError(
                f"地址 {address:#x} 超出内存范围",
                address=address,
                access_type="write"
            )
        
        region = self.get_region(address)
        if region is None:
            raise MemoryAccessError(
                f"地址 {address:#x} 不在任何内存区域内",
                address=address,
                access_type="write"
            )
        
        if region.permission in (MemoryPermission.NONE,
                                  MemoryPermission.READ,
                                  MemoryPermission.READ_EXECUTE):
            raise MemoryAccessError(
                f"地址 {address:#x} 没有写权限",
                address=address,
                access_type="write",
                pmp_region=id(region)
            )
        
        self._data[address] = value & 0xFF
    
    def read_halfword(self, address: int) -> int:
        """读取半字（16 位）.
        
        Args:
            address: 地址（必须 2 字节对齐）
            
        Returns:
            16 位值
            
        Raises:
            MemoryAccessError: 如果访问无效或未对齐
        """
        if address % 2 != 0:
            raise MemoryAccessError(
                f"地址 {address:#x} 未 2 字节对齐",
                address=address,
                access_type="read"
            )
        
        byte0 = self.read_byte(address)
        byte1 = self.read_byte(address + 1)
        return (byte1 << 8) | byte0
    
    def write_halfword(self, address: int, value: int) -> None:
        """写入半字（16 位）.
        
        Args:
            address: 地址（必须 2 字节对齐）
            value: 16 位值
            
        Raises:
            MemoryAccessError: 如果访问无效或未对齐
        """
        if address % 2 != 0:
            raise MemoryAccessError(
                f"地址 {address:#x} 未 2 字节对齐",
                address=address,
                access_type="write"
            )
        
        self.write_byte(address, value & 0xFF)
        self.write_byte(address + 1, (value >> 8) & 0xFF)
    
    def read_word(self, address: int) -> int:
        """读取字（32 位）.
        
        Args:
            address: 地址（必须 4 字节对齐）
            
        Returns:
            32 位值
            
        Raises:
            MemoryAccessError: 如果访问无效或未对齐
        """
        if address % 4 != 0:
            raise MemoryAccessError(
                f"地址 {address:#x} 未 4 字节对齐",
                address=address,
                access_type="read"
            )
        
        byte0 = self.read_byte(address)
        byte1 = self.read_byte(address + 1)
        byte2 = self.read_byte(address + 2)
        byte3 = self.read_byte(address + 3)
        return (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0
    
    def write_word(self, address: int, value: int) -> None:
        """写入字（32 位）.
        
        Args:
            address: 地址（必须 4 字节对齐）
            value: 32 位值
            
        Raises:
            MemoryAccessError: 如果访问无效或未对齐
        """
        if address % 4 != 0:
            raise MemoryAccessError(
                f"地址 {address:#x} 未 4 字节对齐",
                address=address,
                access_type="write"
            )
        
        self.write_byte(address, value & 0xFF)
        self.write_byte(address + 1, (value >> 8) & 0xFF)
        self.write_byte(address + 2, (value >> 16) & 0xFF)
        self.write_byte(address + 3, (value >> 24) & 0xFF)
    
    def read_bytes(self, address: int, length: int) -> bytes:
        """读取多个字节.
        
        Args:
            address: 起始地址
            length: 字节数
            
        Returns:
            字节数据
            
        Raises:
            MemoryAccessError: 如果访问无效
        """
        result = bytearray()
        for i in range(length):
            result.append(self.read_byte(address + i))
        return bytes(result)
    
    def write_bytes(self, address: int, data: bytes) -> None:
        """写入多个字节.
        
        Args:
            address: 起始地址
            data: 字节数据
            
        Raises:
            MemoryAccessError: 如果访问无效
        """
        for i, byte in enumerate(data):
            self.write_byte(address + i, byte)
    
    def load_program(self, address: int, program: bytes) -> None:
        """加载程序到内存.
        
        Args:
            address: 加载地址
            program: 程序字节码
            
        Raises:
            MemoryAccessError: 如果加载失败
        """
        region = self.get_region(address)
        if region is None:
            raise MemoryAccessError(
                f"加载地址 {address:#x} 不在任何内存区域内",
                address=address,
                access_type="write"
            )
        
        if region.permission not in (MemoryPermission.EXECUTE,
                                      MemoryPermission.READ_EXECUTE,
                                      MemoryPermission.ALL):
            raise MemoryAccessError(
                f"内存区域 '{region.name}' 没有执行权限",
                address=address,
                access_type="execute",
                pmp_region=id(region)
            )
        
        self.write_bytes(address, program)
    
    def clear(self) -> None:
        """清空内存."""
        self._data = bytearray(self.size)
    
    def dump(self, start: int, length: int) -> str:
        """转储内存内容.
        
        Args:
            start: 起始地址
            length: 字节数
            
        Returns:
            十六进制转储字符串
        """
        lines = []
        for i in range(0, length, 16):
            addr = start + i
            hex_str = " ".join(
                f"{self._data[addr + j]:02x}" if addr + j < self.size else "  "
                for j in range(16)
            )
            ascii_str = "".join(
                chr(self._data[addr + j]) if addr + j < self.size and 
                32 <= self._data[addr + j] < 127 else "."
                for j in range(16)
            )
            lines.append(f"{addr:08x}: {hex_str}  {ascii_str}")
        return "\n".join(lines)
