"""List command for kdeploy."""

import sys
import click

from kdeploy.config import Config
from kdeploy.utils import (
    print_header,
    print_step,
    print_error,
    print_info,
    ConfigError,
)
from rich.console import Console
from rich.table import Table


@click.command(name='list')
@click.option('--env', '-e', default='test', help='Environment (test, prod, etc.)')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to kdeploy.yaml')
def list_apps(env: str, config: str):
    """List available applications."""
    try:
        # Load configuration
        cfg = Config(config_path=config, environment=env)

        print_header("Available Applications")

        apps = cfg.list_apps()

        if not apps:
            print_info("No applications found")
            print_info(f"Apps directory: {cfg.get_apps_dir()}")
            return

        # Create table
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Application", style="cyan")
        table.add_column("Components", style="dim")
        table.add_column("Config", style="green")

        for app in apps:
            app_dir = cfg.get_apps_dir() / app

            # Find components
            components = []
            for item in app_dir.iterdir():
                if item.is_dir() and (item / "templates").exists():
                    components.append(item.name)

            # Check for flat templates
            if (app_dir / "templates").exists():
                components.insert(0, "(root)")

            components_str = ", ".join(components) if components else "-"

            # Check config
            has_config = (app_dir / "config.yml").exists() or (app_dir / "config.yaml").exists()
            config_str = "✓" if has_config else "✗"

            table.add_row(app, components_str, config_str)

        console.print(table)
        console.print(f"\n[dim]Total: {len(apps)} application(s)[/dim]")

    except ConfigError as e:
        print_error(f"Configuration error: {e}", indent=False)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", indent=False)
        sys.exit(1)
