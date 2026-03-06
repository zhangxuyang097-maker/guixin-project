"""轨芯安项目安装配置."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="railcore-secure",
    version="1.0.0",
    author="RailCore Secure Team",
    author_email="1262599687@qq.com",
    description="面向国产 RISC-V 架构的轨道交通信号安全协议形式化验证工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zhangxuyang097-maker/guixin-project",
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Topic :: Security",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "mypy>=1.5.0",
            "flake8>=6.1.0",
            "black>=23.7.0",
            "isort>=5.12.0",
        ],
        "docs": [
            "sphinx>=7.1.0",
            "sphinx-rtd-theme>=1.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "railcore-verify=core.verification_engine:main",
            "railcore-gui=gui.main_window:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
