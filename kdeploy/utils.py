"""Utility functions for kdeploy."""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.theme import Theme

# Custom theme for rich console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "header": "bold magenta",
    "dim": "dim",
})

console = Console(theme=custom_theme)


def print_header(text: str) -> None:
    """Print a header message."""
    console.print(f"\n[header]{'=' * 50}[/header]")
    console.print(f"[header]{text.center(50)}[/header]")
    console.print(f"[header]{'=' * 50}[/header]\n")


def print_step(text: str) -> None:
    """Print a step message."""
    console.print(f"[info]→[/info] [bold]{text}[/bold]")


def print_success(text: str, indent: bool = True) -> None:
    """Print a success message."""
    prefix = "  " if indent else ""
    console.print(f"{prefix}[success]✓[/success] {text}", markup=False, highlight=False)


def print_error(text: str, indent: bool = True) -> None:
    """Print an error message."""
    prefix = "  " if indent else ""
    # Rich console outputs errors automatically, no need for stderr parameter
    console.print(f"{prefix}[error]✗[/error] {text}", markup=False, highlight=False)


def print_warning(text: str, indent: bool = True) -> None:
    """Print a warning message."""
    prefix = "  " if indent else ""
    console.print(f"{prefix}[warning]⚠[/warning] {text}", markup=False, highlight=False)


def print_info(text: str, indent: bool = True) -> None:
    """Print an info message."""
    prefix = "  " if indent else ""
    console.print(f"{prefix}[dim]{text}[/dim]", highlight=False)


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
