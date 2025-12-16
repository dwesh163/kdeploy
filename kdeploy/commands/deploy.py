"""Deploy command for kdeploy."""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import click

from kdeploy.config import Config
from kdeploy.template import TemplateEngine
from kdeploy.k8s import KubernetesClient
from kdeploy.utils import (
    print_header,
    print_step,
    print_success,
    print_error,
    print_warning,
    print_info,
    ConfigError,
    TemplateError,
    KubernetesError,
)


def _find_environments_for_app(config: Config, app_name: str) -> List[str]:
    """
    Find all environments where an app is configured.

    Args:
        config: Configuration object
        app_name: Application name

    Returns:
        List of environment names
    """
    envs = []
    environments = config.get("environments", {})

    for env_name, env_config in environments.items():
        apps_in_env = env_config.get("apps", [])
        if app_name in apps_in_env:
            envs.append(env_name)

    return envs


@click.command()
@click.argument('app_name', required=False)
@click.option('--env', '-e', default=None, help='Environment. If not specified, deploy to all environments where app is configured.')
@click.option('--namespace', '-n', help='Override namespace')
@click.option('--dry-run', is_flag=True, help='Simulate deployment without applying')
@click.option('--all', 'deploy_all', is_flag=True, help='Deploy all applications')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to kdeploy.yaml')
@click.option('--persist-build', is_flag=True, help='Persist build to disk (default: in-memory only)')
@click.pass_context
def deploy(ctx, app_name: str, env: str, namespace: str, dry_run: bool, deploy_all: bool,
           config: str, persist_build: bool):
    """Deploy application(s) to Kubernetes."""
    try:
        # Get plugin manager from context
        plugin_manager = ctx.obj.get('plugin_manager')

        # Load initial config
        temp_cfg = Config(config_path=config, environment='prod')

        # Determine which environments to deploy to
        envs_to_deploy = []

        if deploy_all:
            # Deploy all apps in all environments
            environments = temp_cfg.get("environments", {})
            envs_to_deploy = list(environments.keys())
        elif app_name:
            if env:
                envs_to_deploy = [env]
            else:
                envs_to_deploy = _find_environments_for_app(temp_cfg, app_name)
                if not envs_to_deploy:
                    environments = temp_cfg.get("environments", {})
                    envs_to_deploy = list(environments.keys())
        else:
            print_error("No application specified. Use --all or provide an app name.", indent=False)
            sys.exit(1)

        # Deploy to each environment
        overall_success = True

        for target_env in envs_to_deploy:
            # Load configuration for this environment
            cfg = Config(config_path=config, environment=target_env)

            # Determine namespace
            target_namespace = namespace or cfg.get_namespace()
            if not target_namespace:
                print_error(f"No namespace for environment {target_env}", indent=False)
                overall_success = False
                continue

            print_header(f"Deploying to {target_env} ({target_namespace})")

            # Initialize Kubernetes client
            k8s = KubernetesClient(cfg)

            # Check prerequisites
            print_step("Checking prerequisites")
            success, message = k8s.check_connection()
            if not success:
                print_error(message)
                overall_success = False
                continue
            print_success(message)

            if not k8s.check_namespace(target_namespace):
                print_error(f"Namespace '{target_namespace}' does not exist")
                overall_success = False
                continue
            print_success(f"Namespace: {target_namespace}")

            if dry_run:
                print_warning("Dry-run mode: no changes will be applied")

            print()

            # Deploy app(s)
            if deploy_all:
                apps = cfg.get_env_config("apps", cfg.list_apps())
                if not apps:
                    print_error("No applications found", indent=False)
                    overall_success = False
                    continue

                success_count = 0
                failed_count = 0

                for app in apps:
                    try:
                        if _deploy_single_app(
                            app, cfg, k8s, target_namespace, dry_run, persist_build, plugin_manager
                        ):
                            success_count += 1
                        else:
                            failed_count += 1
                            overall_success = False
                    except Exception as e:
                        print_error(f"Failed to deploy {app}: {e}")
                        failed_count += 1
                        overall_success = False

                print()
                print_step(f"Environment {target_env} Summary")
                print_info(f"Total: {len(apps)}")
                print_success(f"Successful: {success_count}")
                if failed_count > 0:
                    print_error(f"Failed: {failed_count}")

            else:
                apps = cfg.list_apps()
                if app_name not in apps:
                    print_error(f"Application '{app_name}' not found", indent=False)
                    print_info(f"Available apps: {', '.join(apps)}")
                    overall_success = False
                    continue

                if not _deploy_single_app(
                    app_name, cfg, k8s, target_namespace, dry_run, persist_build, plugin_manager
                ):
                    overall_success = False

            print()

        if overall_success:
            print_success("All deployments complete!", indent=False)
        else:
            print_error("Some deployments failed", indent=False)
            sys.exit(1)

    except ConfigError as e:
        print_error(f"Configuration error: {e}", indent=False)
        sys.exit(1)
    except KubernetesError as e:
        print_error(f"Kubernetes error: {e}", indent=False)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", indent=False)
        sys.exit(1)


def _deploy_single_app(
    app_name: str,
    cfg: Config,
    k8s: KubernetesClient,
    namespace: str,
    dry_run: bool,
    persist_build: bool,
    plugin_manager
) -> bool:
    """
    Deploy a single application.

    Returns:
        True if deployment successful
    """
    print_step(f"Deploying {app_name}")

    # Call pre-deploy hooks
    if plugin_manager:
        plugin_manager.call_hook('kdeploy_pre_deploy', app_name=app_name, config=cfg, namespace=namespace)

    # Build templates (in-memory by default, or persist if requested)
    try:
        engine = TemplateEngine(cfg)
        template_count, rendered_templates = engine.render_app_templates(
            app_name,
            in_memory=not persist_build
        )
        print_success(f"Built {template_count} templates")
        if persist_build:
            print_info(f"Persisted to: {cfg.get_build_dir() / app_name}")
    except TemplateError as e:
        print_error(f"Build failed: {e}")
        return False

    # Deploy manifests
    stats = {
        'created': 0,
        'configured': 0,
        'unchanged': 0,
        'error': 0,
    }

    needs_rollout = False

    # Sort by filename for consistent ordering
    sorted_templates = sorted(rendered_templates.items(), key=lambda x: str(x[0]))

    for rel_path, content in sorted_templates:
        try:
            status, message = k8s.apply_manifest(
                manifest_content=content,
                namespace=namespace,
                dry_run=dry_run
            )
            stats[status] = stats.get(status, 0) + 1

            if status == 'created':
                print_success(f"{rel_path} (created)")
            elif status == 'configured':
                print_success(f"{rel_path} (configured)")
                # Check if we need rollout restart
                if 'configmap' in str(rel_path).lower() or 'secret' in str(rel_path).lower():
                    needs_rollout = True
            elif status == 'unchanged':
                print_info(f"{rel_path} (unchanged)")
            else:
                print_error(f"{rel_path}: {message}")

        except Exception as e:
            print_error(f"{rel_path}: {e}")
            stats['error'] = stats.get('error', 0) + 1

    # Print stats
    print_info(
        f"Results: {stats.get('created', 0)} created, "
        f"{stats.get('configured', 0)} configured, "
        f"{stats.get('unchanged', 0)} unchanged, "
        f"{stats.get('error', 0)} errors"
    )

    # Rollout restart if needed
    if needs_rollout and not dry_run:
        print_step("Restarting deployments due to ConfigMap/Secret changes")
        # Find deployments in rendered templates
        for rel_path, content in rendered_templates.items():
            if 'deployment' in str(rel_path).lower():
                try:
                    import yaml
                    for doc in yaml.safe_load_all(content):
                        if doc and doc.get('kind') == 'Deployment':
                            deploy_name = doc['metadata']['name']
                            if k8s.rollout_restart(deploy_name, namespace):
                                print_success(f"Restarted: {deploy_name}")
                except Exception:
                    pass

    # Call post-deploy hooks
    success = stats.get('error', 0) == 0
    if plugin_manager:
        plugin_manager.call_hook(
            'kdeploy_post_deploy',
            app_name=app_name,
            config=cfg,
            namespace=namespace,
            success=success,
            stats=stats
        )

    return success
