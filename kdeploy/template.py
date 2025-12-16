"""Template rendering engine for kdeploy."""

import base64
from pathlib import Path
from typing import Dict, Any, Optional
import jinja2
import yaml

from kdeploy.utils import TemplateError, ensure_directory
from kdeploy.config import Config


class TemplateEngine:
    """Template rendering engine using Jinja2."""

    def __init__(self, config: Config):
        """
        Initialize template engine.

        Args:
            config: Configuration manager
        """
        self.config = config
        self._env: Optional[jinja2.Environment] = None

    def _get_jinja_env(self, templates_dir: Path) -> jinja2.Environment:
        """
        Get or create Jinja2 environment.

        Args:
            templates_dir: Templates directory path

        Returns:
            Jinja2 environment
        """
        loader = jinja2.FileSystemLoader(str(templates_dir))

        env = jinja2.Environment(
            loader=loader,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # Add custom filters
        env.filters['b64encode'] = self._b64encode_filter
        env.filters['b64decode'] = self._b64decode_filter
        env.filters['b64'] = self._b64encode_filter  # Alias for compatibility

        return env

    @staticmethod
    def _b64encode_filter(value: str) -> str:
        """Base64 encode filter for Jinja2."""
        if not value:
            return ""
        return base64.b64encode(value.encode('utf-8')).decode('ascii')

    @staticmethod
    def _b64decode_filter(value: str) -> str:
        """Base64 decode filter for Jinja2."""
        if not value:
            return ""
        return base64.b64decode(value.encode('ascii')).decode('utf-8')

    def render_template(
        self,
        template_path: Path,
        output_path: Optional[Path],
        context: Dict[str, Any]
    ) -> str:
        """
        Render a single template file.

        Args:
            template_path: Path to template file
            output_path: Path to output file (None for in-memory only)
            context: Template context variables

        Returns:
            Rendered template content as string
        """
        if not template_path.exists():
            raise TemplateError(f"Template not found: {template_path}")

        try:
            # Get Jinja2 environment with template directory as loader path
            env = self._get_jinja_env(template_path.parent)

            # Load and render template
            template = env.get_template(template_path.name)
            rendered = template.render(**context)

            # Write to file only if output_path is specified
            if output_path:
                ensure_directory(output_path.parent)
                with open(output_path, 'w') as f:
                    f.write(rendered)

            return rendered

        except jinja2.TemplateError as e:
            raise TemplateError(f"Failed to render template {template_path}: {e}")
        except IOError as e:
            raise TemplateError(f"Failed to write output {output_path}: {e}")

    def build_context(
        self,
        app_name: str,
        component: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build template context for an application.

        Args:
            app_name: Application name
            component: Component name (optional)

        Returns:
            Template context dictionary
        """
        context: Dict[str, Any] = {
            "app": {"name": app_name},
            "env": self.config.environment,
            "namespace": self.config.get_namespace(),
            "global": {},
            "config": {},
            "secret": {},
        }

        # Load app config
        app_config = self.config.get_app_config(app_name)
        if app_config:
            context["config"] = app_config
            # Merge flat config into app for compatibility
            # This allows {{ app.namespace }}, {{ app.url }}, etc.
            context["app"].update(app_config)
            # Also support nested app.* from config
            if "app" in app_config:
                context["app"].update(app_config["app"])

        # Override namespace if defined in app config
        if "namespace" in context["app"]:
            context["namespace"] = context["app"]["namespace"]
        else:
            # Ensure app.namespace is set from environment namespace
            context["app"]["namespace"] = context["namespace"]

        # Load component config if specified
        if component:
            component_config_path = (
                self.config.get_apps_dir() / app_name / component / "config.yml"
            )
            if not component_config_path.exists():
                component_config_path = component_config_path.with_suffix(".yaml")

            if component_config_path.exists():
                try:
                    with open(component_config_path, 'r') as f:
                        comp_config = yaml.safe_load(f) or {}
                        context["component"] = comp_config
                except (yaml.YAMLError, IOError):
                    pass

        # Load secrets for the app
        app_secrets = self.config._secrets.get(app_name, {})
        context["secret"] = app_secrets

        # Load global secrets
        global_secrets = self.config._secrets.get("global", {})
        context["global"] = global_secrets

        # Add environment-specific config
        env_config = self.config.get(f"environments.{self.config.environment}", {})
        if env_config:
            for key, value in env_config.items():
                if key not in context:
                    context[key] = value

        return context

    def render_app_templates(
        self,
        app_name: str,
        output_dir: Optional[Path] = None,
        in_memory: bool = False
    ) -> tuple[int, Dict[Path, str]]:
        """
        Render all templates for an application.

        Args:
            app_name: Application name
            output_dir: Output directory (defaults to build/<app_name>)
            in_memory: If True, keep templates in memory without writing to disk

        Returns:
            Tuple of (template_count, rendered_templates_dict)
            rendered_templates_dict maps relative paths to rendered content
        """
        apps_dir = self.config.get_apps_dir()
        app_dir = apps_dir / app_name

        if not app_dir.exists():
            raise TemplateError(f"Application directory not found: {app_dir}")

        if output_dir is None and not in_memory:
            output_dir = self.config.get_build_dir() / app_name

        # Clean output directory (only if persisting to disk)
        if output_dir and not in_memory:
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
            ensure_directory(output_dir)

        template_count = 0
        rendered_templates: Dict[Path, str] = {}

        # Find all component directories with templates
        for component_dir in app_dir.iterdir():
            if not component_dir.is_dir():
                continue

            component_name = component_dir.name
            templates_dir = component_dir / "templates"

            if not templates_dir.exists():
                continue

            # Build context for this component
            context = self.build_context(app_name, component_name)

            # Create component output directory
            component_output_dir = output_dir / component_name
            ensure_directory(component_output_dir)

            # Render all template files
            for template_file in templates_dir.rglob("*.y*ml"):
                if not template_file.is_file():
                    continue

                # Preserve subdirectory structure
                rel_path = template_file.relative_to(templates_dir)

                if in_memory:
                    # Render in memory only
                    rendered = self.render_template(template_file, None, context)
                    # Store with component name in path
                    output_rel_path = Path(component_name) / rel_path
                    rendered_templates[output_rel_path] = rendered
                else:
                    # Render to disk
                    output_file = component_output_dir / rel_path
                    rendered = self.render_template(template_file, output_file, context)
                    rendered_templates[Path(component_name) / rel_path] = rendered

                template_count += 1

        # Also support flat structure (templates in app root)
        templates_dir = app_dir / "templates"
        if templates_dir.exists():
            context = self.build_context(app_name)

            for template_file in templates_dir.rglob("*.y*ml"):
                if not template_file.is_file():
                    continue

                rel_path = template_file.relative_to(templates_dir)

                if in_memory:
                    # Render in memory only
                    rendered = self.render_template(template_file, None, context)
                    rendered_templates[rel_path] = rendered
                else:
                    # Render to disk
                    output_file = output_dir / rel_path
                    rendered = self.render_template(template_file, output_file, context)
                    rendered_templates[rel_path] = rendered

                template_count += 1

        return template_count, rendered_templates
