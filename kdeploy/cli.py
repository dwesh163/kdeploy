"""Main CLI for kdeploy."""

import sys
from pathlib import Path
import click

from kdeploy import __version__
from kdeploy.utils import print_header, print_error, find_ops_root
from kdeploy.plugins import PluginManager
from kdeploy.commands import build, deploy, list_apps, status


@click.group()
@click.version_option(version=__version__, prog_name='kdeploy')
@click.option('--plugins-dir', type=click.Path(exists=True), help='Path to plugins directory')
@click.pass_context
def cli(ctx, plugins_dir: str):
    """
    kdeploy - Extensible Kubernetes deployment CLI tool.

    A modern, Ansible-inspired deployment tool for Kubernetes with
    multi-environment support, template rendering, and extensibility.
    """
    # Initialize context
    ctx.ensure_object(dict)

    # Find ops root
    ops_root = find_ops_root()

    # Determine plugin directories
    plugin_dirs = []

    # Add global plugins directory
    if plugins_dir:
        plugin_dirs.append(Path(plugins_dir))

    # Add ops-local plugins directory
    if ops_root:
        local_plugins = ops_root / "plugins"
        if local_plugins.exists():
            plugin_dirs.append(local_plugins)

    # Add built-in plugins directory
    builtin_plugins = Path(__file__).parent.parent / "plugins"
    if builtin_plugins.exists():
        plugin_dirs.append(builtin_plugins)

    # Initialize plugin manager
    plugin_manager = PluginManager(plugin_dirs)
    plugin_manager.load_plugins()

    # Store plugin manager in context
    ctx.obj['plugin_manager'] = plugin_manager

    # Load custom commands from plugins
    custom_commands = plugin_manager.get_custom_commands()
    for cmd_name, cmd_func in custom_commands.items():
        if cmd_name not in cli.commands:
            cli.add_command(cmd_func, name=cmd_name)


# Add built-in commands
cli.add_command(build)
cli.add_command(deploy)
cli.add_command(list_apps)
cli.add_command(status)


def main():
    """Main entry point for kdeploy CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        print_error("\nInterrupted by user", indent=False)
        sys.exit(130)
    except Exception as e:
        print_error(f"Fatal error: {e}", indent=False)
        sys.exit(1)


if __name__ == '__main__':
    main()
