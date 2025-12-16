"""Status command for kdeploy."""

import sys
import click

from kdeploy.config import Config
from kdeploy.k8s import KubernetesClient
from kdeploy.utils import (
    print_header,
    print_step,
    print_success,
    print_error,
    print_info,
    ConfigError,
    KubernetesError,
)
from rich.console import Console
from rich.table import Table
from kubernetes import client


@click.command()
@click.option('--env', '-e', default='test', help='Environment (test, prod, etc.)')
@click.option('--namespace', '-n', help='Override namespace')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to kdeploy.yaml')
@click.option('--app', '-a', help='Filter by application name')
def status(env: str, namespace: str, config: str, app: str):
    """Show cluster and deployment status."""
    try:
        # Load configuration
        cfg = Config(config_path=config, environment=env)

        # Determine namespace
        if not namespace:
            namespace = cfg.get_namespace()
            if not namespace:
                print_error("No namespace specified and none found in config", indent=False)
                sys.exit(1)

        print_header(f"Status - {env} ({namespace})")

        # Initialize Kubernetes client
        k8s = KubernetesClient(cfg)

        # Check connection
        print_step("Checking cluster connection")
        success, message = k8s.check_connection()
        if not success:
            print_error(message)
            sys.exit(1)
        print_success(message)
        print()

        # Get pods
        print_step(f"Pods in namespace: {namespace}")
        _show_pods(namespace, app)
        print()

        # Get services
        print_step(f"Services in namespace: {namespace}")
        _show_services(namespace, app)
        print()

        # Get deployments
        print_step(f"Deployments in namespace: {namespace}")
        _show_deployments(namespace, app)
        print()

    except ConfigError as e:
        print_error(f"Configuration error: {e}", indent=False)
        sys.exit(1)
    except KubernetesError as e:
        print_error(f"Kubernetes error: {e}", indent=False)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", indent=False)
        sys.exit(1)


def _show_pods(namespace: str, app_filter: str = None):
    """Show pods in namespace."""
    try:
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=namespace)

        if not pods.items:
            print_info("No pods found")
            return

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Restarts", style="yellow")
        table.add_column("Age", style="dim")

        for pod in pods.items:
            pod_name = pod.metadata.name

            # Filter by app if specified
            if app_filter and app_filter not in pod_name:
                continue

            # Get status
            phase = pod.status.phase
            if phase == "Running":
                status_style = "green"
            elif phase == "Pending":
                status_style = "yellow"
            else:
                status_style = "red"

            # Get restarts
            restarts = sum(
                cs.restart_count for cs in pod.status.container_statuses
            ) if pod.status.container_statuses else 0

            # Calculate age
            age = _format_age(pod.metadata.creation_timestamp)

            table.add_row(
                pod_name,
                f"[{status_style}]{phase}[/{status_style}]",
                str(restarts),
                age
            )

        console.print(table)

    except Exception as e:
        print_error(f"Failed to list pods: {e}")


def _show_services(namespace: str, app_filter: str = None):
    """Show services in namespace."""
    try:
        v1 = client.CoreV1Api()
        services = v1.list_namespaced_service(namespace=namespace)

        if not services.items:
            print_info("No services found")
            return

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="white")
        table.add_column("Cluster IP", style="white")
        table.add_column("Ports", style="dim")

        for svc in services.items:
            svc_name = svc.metadata.name

            # Filter by app if specified
            if app_filter and app_filter not in svc_name:
                continue

            svc_type = svc.spec.type
            cluster_ip = svc.spec.cluster_ip or "-"

            # Get ports
            ports = []
            if svc.spec.ports:
                for port in svc.spec.ports:
                    port_str = f"{port.port}"
                    if port.target_port:
                        port_str += f":{port.target_port}"
                    if port.protocol and port.protocol != "TCP":
                        port_str += f"/{port.protocol}"
                    ports.append(port_str)

            ports_str = ", ".join(ports) if ports else "-"

            table.add_row(svc_name, svc_type, cluster_ip, ports_str)

        console.print(table)

    except Exception as e:
        print_error(f"Failed to list services: {e}")


def _show_deployments(namespace: str, app_filter: str = None):
    """Show deployments in namespace."""
    try:
        apps_v1 = client.AppsV1Api()
        deployments = apps_v1.list_namespaced_deployment(namespace=namespace)

        if not deployments.items:
            print_info("No deployments found")
            return

        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan")
        table.add_column("Ready", style="white")
        table.add_column("Up-to-date", style="white")
        table.add_column("Available", style="white")
        table.add_column("Age", style="dim")

        for deploy in deployments.items:
            deploy_name = deploy.metadata.name

            # Filter by app if specified
            if app_filter and app_filter not in deploy_name:
                continue

            replicas = deploy.spec.replicas or 0
            ready_replicas = deploy.status.ready_replicas or 0
            updated_replicas = deploy.status.updated_replicas or 0
            available_replicas = deploy.status.available_replicas or 0

            # Format ready status with color
            if ready_replicas == replicas and replicas > 0:
                ready_str = f"[green]{ready_replicas}/{replicas}[/green]"
            elif ready_replicas > 0:
                ready_str = f"[yellow]{ready_replicas}/{replicas}[/yellow]"
            else:
                ready_str = f"[red]{ready_replicas}/{replicas}[/red]"

            age = _format_age(deploy.metadata.creation_timestamp)

            table.add_row(
                deploy_name,
                ready_str,
                str(updated_replicas),
                str(available_replicas),
                age
            )

        console.print(table)

    except Exception as e:
        print_error(f"Failed to list deployments: {e}")


def _format_age(timestamp) -> str:
    """Format Kubernetes timestamp to age string."""
    from datetime import datetime, timezone

    if not timestamp:
        return "-"

    now = datetime.now(timezone.utc)
    delta = now - timestamp

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days}d"
    elif hours > 0:
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "< 1m"
