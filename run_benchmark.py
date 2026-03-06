#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""轨芯安全套基准测试运行脚本.

直接运行此脚本执行完整的基准测试套件。

用法:
    python run_benchmark.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.benchmark import run_benchmark


if __name__ == "__main__":
    report = run_benchmark()
    sys.exit(0 if report["is_qualified"] else 1)
