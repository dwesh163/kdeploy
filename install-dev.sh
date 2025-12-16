#!/bin/bash
# Development installation script for kdeploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  kdeploy Development Installation"
echo "========================================"
echo

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python version: $PYTHON_VERSION"

# Check if we're in Arch Linux with externally-managed environment
if [[ -f /etc/arch-release ]]; then
    echo "✓ Detected Arch Linux"

    # Check if pipx is available
    if command -v pipx &> /dev/null; then
        echo "✓ pipx is available"
        echo
        echo "Installing kdeploy using pipx (recommended for Arch Linux)..."
        pipx install -e .
        echo
        echo "✓ kdeploy installed successfully!"
        echo
        echo "To uninstall: pipx uninstall kdeploy"
        exit 0
    else
        echo
        echo "Note: For Arch Linux, it's recommended to install pipx first:"
        echo "  sudo pacman -S python-pipx"
        echo
        echo "Continuing with virtual environment installation..."
    fi
fi

# Create virtual environment
VENV_DIR="$SCRIPT_DIR/venv"

if [[ -d "$VENV_DIR" ]]; then
    echo "Virtual environment already exists at: $VENV_DIR"
    read -p "Remove and recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
    else
        echo "Using existing virtual environment"
    fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install kdeploy in development mode
echo "Installing kdeploy in development mode..."
pip install -e ".[dev]"

echo
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo
echo "To use kdeploy:"
echo "  1. Activate the virtual environment:"
echo "     source $VENV_DIR/bin/activate"
echo
echo "  2. Run kdeploy:"
echo "     kdeploy --help"
echo
echo "To make kdeploy available globally, add an alias to your ~/.bashrc or ~/.zshrc:"
echo "  alias kdeploy='$VENV_DIR/bin/kdeploy'"
echo
echo "Or create a symlink:"
echo "  sudo ln -s $VENV_DIR/bin/kdeploy /usr/local/bin/kdeploy"
echo
