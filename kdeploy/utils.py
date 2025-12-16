"""Utility functions for kdeploy."""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.theme import Theme

# Custom theme for rich console
custom_theme = Theme({
    "arrow": "cyan",
    "check": "green",
    "cross": "red",
    "info_icon": "blue",
    "warn": "bright_yellow",
    "header": "bold cyan",
    "dim": "dim",
})

console = Console(theme=custom_theme)


def print_header(text: str) -> None:
    """Print a header message."""
    from rich.text import Text
    line = Text("=" * 50, style="header")
    title = Text(text.center(50), style="header")
    console.print()
    console.print(line)
    console.print(title)
    console.print(line)
    console.print()


def print_step(text: str) -> None:
    """Print a step message."""
    from rich.text import Text
    arrow = Text("→ ", style="arrow")
    msg = Text(text, style="bold")
    console.print(arrow + msg)


def print_success(text: str, indent: bool = True) -> None:
    """Print a success message."""
    from rich.text import Text
    prefix = "  " if indent else ""
    check = Text(f"{prefix}✓ ", style="check")
    msg = Text(text)
    console.print(check + msg, highlight=False)


def print_error(text: str, indent: bool = True) -> None:
    """Print an error message."""
    from rich.text import Text
    prefix = "  " if indent else ""
    cross = Text(f"{prefix}✗ ", style="cross")
    msg = Text(text)
    console.print(cross + msg, highlight=False)


def print_warning(text: str, indent: bool = True) -> None:
    """Print a warning message."""
    from rich.text import Text
    prefix = "  " if indent else ""
    warn = Text(f"{prefix}⚠ ", style="warn")
    msg = Text(text)
    console.print(warn + msg, highlight=False)


def print_info(text: str, indent: bool = True) -> None:
    """Print an info message."""
    from rich.text import Text
    prefix = "  " if indent else ""
    icon = Text(f"{prefix}ℹ ", style="info_icon")
    msg = Text(text, style="dim")
    console.print(icon + msg, highlight=False)


def find_ops_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find the ops root directory by looking for kdeploy.yaml.

    Args:
        start_path: Starting path for search (defaults to current directory)

    Returns:
        Path to ops root directory or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Search up to 5 levels
    for _ in range(5):
        if (current / "kdeploy.yaml").exists() or (current / "kdeploy.yml").exists():
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    return None


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get environment variable with optional default.

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return os.environ.get(key, default)


def deep_merge(base: Dict[Any, Any], override: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def ensure_directory(path: Path) -> None:
    """
    Ensure directory exists, create if it doesn't.

    Args:
        path: Directory path
    """
    path.mkdir(parents=True, exist_ok=True)


class KDeployError(Exception):
    """Base exception for kdeploy errors."""
    pass


class ConfigError(KDeployError):
    """Configuration related error."""
    pass


class TemplateError(KDeployError):
    """Template rendering error."""
    pass


class KubernetesError(KDeployError):
    """Kubernetes operation error."""
    pass
