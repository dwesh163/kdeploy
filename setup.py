#!/usr/bin/env python3
"""Setup script for kdeploy - Kubernetes deployment CLI tool."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="kdeploy",
    version="0.1.0",
    author="dwesh163",
    description="Extensible Kubernetes deployment CLI tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dwesh163/kdeploy",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "jinja2>=3.0.0",
        "kubernetes>=25.0.0",
        "rich>=13.0.0",
        "pluggy>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kdeploy=kdeploy.cli:main",
        ],
    },
    include_package_data=True,
)
