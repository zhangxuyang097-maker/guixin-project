"""GUI 模块.

提供 PyQt6 实现的图形用户界面，支持协议可视化、
验证结果展示和仿真控制。
"""

from .main_window import MainWindow
from .verification_widget import VerificationWidget
from .simulation_widget import SimulationWidget

__all__ = [
    "MainWindow",
    "VerificationWidget",
    "SimulationWidget",
]
