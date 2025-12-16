"""Build command for kdeploy."""

import sys
import click

from kdeploy.config import Config
from kdeploy.template import TemplateEngine
from kdeploy.utils import (
    print_header,
    print_step,
    print_success,
    print_error,
    print_info,
    ConfigError,
    TemplateError,
)


@click.command()
@click.argument('app_name')
@click.option('--env', '-e', default='test', help='Environment (test, prod, etc.)')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to kdeploy.yaml')
@click.pass_context
def build(ctx, app_name: str, env: str, config: str):
    """Build application templates."""
    try:
        # Load configuration
        cfg = Config(config_path=config, environment=env)

        # Get plugin manager from context
        plugin_manager = ctx.obj.get('plugin_manager')

        print_header(f"Building {app_name}")

        # Call pre-build hooks
        if plugin_manager:
            plugin_manager.call_hook('kdeploy_pre_build', app_name=app_name, config=cfg)

        # Check if app exists
        apps = cfg.list_apps()
        if app_name not in apps:
            print_error(f"Application '{app_name}' not found", indent=False)
            print_info(f"Available apps: {', '.join(apps)}")
            sys.exit(1)

        # Initialize template engine
        engine = TemplateEngine(cfg)

        # Render templates (persist to disk for build command)
        print_step(f"Rendering templates for {app_name}")
        template_count, _ = engine.render_app_templates(app_name, in_memory=False)

        print_success(f"Rendered {template_count} template(s)")
        print_info(f"Output: {cfg.get_build_dir() / app_name}")

        # Call post-build hooks
        if plugin_manager:
            plugin_manager.call_hook(
                'kdeploy_post_build',
                app_name=app_name,
                config=cfg,
                template_count=template_count
            )

        print_success(f"\nBuild complete for {app_name}", indent=False)

    except ConfigError as e:
        print_error(f"Configuration error: {e}", indent=False)
        sys.exit(1)
    except TemplateError as e:
        print_error(f"Template error: {e}", indent=False)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", indent=False)
        sys.exit(1)
