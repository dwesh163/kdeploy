"""Kubernetes client wrapper for kdeploy."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import yaml
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

from kdeploy.utils import KubernetesError, print_info, print_warning
from kdeploy.config import Config


class KubernetesClient:
    """Kubernetes client wrapper."""

    def __init__(self, cfg: Config):
        """
        Initialize Kubernetes client.

        Args:
            cfg: Configuration manager
        """
        self.cfg = cfg
        self._api_client: Optional[client.ApiClient] = None
        self._load_kubeconfig()

    def _load_kubeconfig(self) -> None:
        """Load kubeconfig from file or in-cluster config."""
        kubeconfig_path = self.cfg.get_kubeconfig()

        try:
            if kubeconfig_path and os.path.exists(kubeconfig_path):
                k8s_config.load_kube_config(config_file=kubeconfig_path)
            else:
                # Try in-cluster config
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    # Fall back to default kubeconfig
                    k8s_config.load_kube_config()

            self._api_client = client.ApiClient()

        except Exception as e:
            raise KubernetesError(f"Failed to load kubeconfig: {e}")

    def check_connection(self) -> Tuple[bool, str]:
        """
        Check connection to Kubernetes cluster.

        Returns:
            Tuple of (success, message)
        """
        try:
            v1 = client.VersionApi(self._api_client)
            version = v1.get_code()
            context = k8s_config.list_kube_config_contexts()[1]['name']
            # Escape brackets to prevent Rich from interpreting as markup
            context_safe = context.replace('[', '\\[').replace(']', '\\]')
            version_safe = version.git_version.replace('[', '\\[').replace(']', '\\]')
            return True, f"Connected to cluster (context: {context_safe}, version: {version_safe})"
        except Exception as e:
            return False, f"Failed to connect to cluster: {e}"

    def check_namespace(self, namespace: str) -> bool:
        """
        Check if namespace exists.

        Args:
            namespace: Namespace name

        Returns:
            True if namespace exists
        """
        try:
            v1 = client.CoreV1Api(self._api_client)
            v1.read_namespace(name=namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise KubernetesError(f"Failed to check namespace: {e}")

    def apply_manifest(
        self,
        manifest_path: Optional[Path] = None,
        manifest_content: Optional[str] = None,
        namespace: str = None,
        dry_run: bool = False
    ) -> Tuple[str, str]:
        """
        Apply a Kubernetes manifest from file or content.

        Args:
            manifest_path: Path to manifest file (optional if manifest_content provided)
            manifest_content: Manifest content as string (optional if manifest_path provided)
            namespace: Namespace to apply to
            dry_run: If True, only validate without applying

        Returns:
            Tuple of (status, message) where status is 'created', 'configured', or 'unchanged'
        """
        if manifest_path and not manifest_content:
            if not manifest_path.exists():
                raise KubernetesError(f"Manifest not found: {manifest_path}")
            with open(manifest_path, 'r') as f:
                content = f.read()
        elif manifest_content:
            content = manifest_content
        else:
            raise KubernetesError("Either manifest_path or manifest_content must be provided")

        try:
            manifests = list(yaml.safe_load_all(content))

            results = []
            for manifest in manifests:
                if not manifest:
                    continue

                kind = manifest.get('kind', 'Unknown')
                metadata = manifest.get('metadata', {})
                name = metadata.get('name', 'unknown')

                # Override namespace if specified in manifest
                manifest_namespace = metadata.get('namespace', namespace)

                # Get appropriate API based on kind
                result = self._apply_resource(
                    manifest,
                    manifest_namespace,
                    dry_run
                )
                results.append((kind, name, result))

            # Summarize results
            if len(results) == 1:
                kind, name, (status, msg) = results[0]
                return status, f"{kind}/{name} {msg}"
            else:
                status_counts = {}
                for _, _, (status, _) in results:
                    status_counts[status] = status_counts.get(status, 0) + 1

                status_str = ", ".join(f"{count} {status}" for status, count in status_counts.items())
                return "configured", f"Applied {len(results)} resources: {status_str}"

        except yaml.YAMLError as e:
            raise KubernetesError(f"Failed to parse manifest: {e}")
        except Exception as e:
            raise KubernetesError(f"Failed to apply manifest: {e}")

    def _apply_resource(
        self,
        manifest: Dict[str, Any],
        namespace: str,
        dry_run: bool = False
    ) -> Tuple[str, str]:
        """
        Apply a single Kubernetes resource.

        Args:
            manifest: Resource manifest dictionary
            namespace: Namespace to apply to
            dry_run: If True, only validate without applying

        Returns:
            Tuple of (status, message)
        """
        kind = manifest.get('kind')
        api_version = manifest.get('apiVersion')
        metadata = manifest.get('metadata', {})
        name = metadata.get('name')

        if not all([kind, api_version, name]):
            return "error", "Invalid manifest: missing required fields"

        try:
            # Determine API client
            if '/' not in api_version:
                # Core API
                api_client = client.CoreV1Api(self._api_client)
            else:
                # Other APIs (apps/v1, batch/v1, etc.)
                api_group = api_version.split('/')[0]
                if api_group == 'apps':
                    api_client = client.AppsV1Api(self._api_client)
                elif api_group == 'batch':
                    api_client = client.BatchV1Api(self._api_client)
                elif api_group == 'networking.k8s.io':
                    api_client = client.NetworkingV1Api(self._api_client)
                else:
                    # Use dynamic client for custom resources
                    return self._apply_custom_resource(manifest, namespace, dry_run)

            # Check if resource exists
            exists = self._resource_exists(api_client, kind, name, namespace)

            # Prepare dry run parameter
            dry_run_param = "All" if dry_run else None

            # Apply resource
            if exists:
                # Update existing resource
                if kind == 'Deployment':
                    api_client.patch_namespaced_deployment(
                        name=name,
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Service':
                    api_client.patch_namespaced_service(
                        name=name,
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'ConfigMap':
                    api_client.patch_namespaced_config_map(
                        name=name,
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Secret':
                    api_client.patch_namespaced_secret(
                        name=name,
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Ingress':
                    api_client.patch_namespaced_ingress(
                        name=name,
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                else:
                    return "error", f"Unsupported resource kind for update: {kind}"

                return "configured", "configured"
            else:
                # Create new resource
                if kind == 'Deployment':
                    api_client.create_namespaced_deployment(
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Service':
                    api_client.create_namespaced_service(
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'ConfigMap':
                    api_client.create_namespaced_config_map(
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Secret':
                    api_client.create_namespaced_secret(
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                elif kind == 'Ingress':
                    api_client.create_namespaced_ingress(
                        namespace=namespace,
                        body=manifest,
                        dry_run=dry_run_param
                    )
                else:
                    return "error", f"Unsupported resource kind for create: {kind}"

                return "created", "created"

        except ApiException as e:
            if e.status == 409:  # Conflict - resource already exists
                return "unchanged", "unchanged"
            else:
                return "error", f"API error: {e.reason}"
        except Exception as e:
            return "error", str(e)

    def _resource_exists(
        self,
        api_client: Any,
        kind: str,
        name: str,
        namespace: str
    ) -> bool:
        """Check if a resource exists."""
        try:
            if kind == 'Deployment':
                api_client.read_namespaced_deployment(name=name, namespace=namespace)
            elif kind == 'Service':
                api_client.read_namespaced_service(name=name, namespace=namespace)
            elif kind == 'ConfigMap':
                api_client.read_namespaced_config_map(name=name, namespace=namespace)
            elif kind == 'Secret':
                api_client.read_namespaced_secret(name=name, namespace=namespace)
            elif kind == 'Ingress':
                api_client.read_namespaced_ingress(name=name, namespace=namespace)
            else:
                return False
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def _apply_custom_resource(
        self,
        manifest: Dict[str, Any],
        namespace: str,
        dry_run: bool = False
    ) -> Tuple[str, str]:
        """Apply custom resource using dynamic client."""
        try:
            from kubernetes import dynamic
            from kubernetes.client import api_client

            dyn_client = dynamic.DynamicClient(self._api_client)

            api_version = manifest.get('apiVersion', '')
            kind = manifest.get('kind', '')
            name = manifest.get('metadata', {}).get('name', '')

            # Get API resource
            api_resource = dyn_client.resources.get(
                api_version=api_version,
                kind=kind
            )

            # Check if resource exists
            try:
                existing = api_resource.get(name=name, namespace=namespace)
                exists = True
            except Exception:
                exists = False

            # Apply resource
            dry_run_param = ['All'] if dry_run else None

            if exists:
                # Patch existing resource
                api_resource.patch(
                    body=manifest,
                    name=name,
                    namespace=namespace,
                    dry_run=dry_run_param
                )
                return "configured", "configured"
            else:
                # Create new resource
                api_resource.create(
                    body=manifest,
                    namespace=namespace,
                    dry_run=dry_run_param
                )
                return "created", "created"

        except Exception as e:
            # If dynamic client fails, try kubectl-style apply
            return self._apply_via_kubectl(manifest, namespace, dry_run)

    def _apply_via_kubectl(
        self,
        manifest: Dict[str, Any],
        namespace: str,
        dry_run: bool = False
    ) -> Tuple[str, str]:
        """Fallback: apply resource via kubectl command."""
        import subprocess
        import tempfile
        import yaml

        try:
            # Write manifest to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(manifest, f)
                temp_file = f.name

            # Build kubectl command
            cmd = ['kubectl', 'apply', '-f', temp_file, '-n', namespace]
            if dry_run:
                cmd.append('--dry-run=server')

            # Execute kubectl
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Clean up temp file
            import os
            os.unlink(temp_file)

            if result.returncode == 0:
                output = result.stdout.lower()
                if 'created' in output:
                    return "created", "created"
                elif 'configured' in output:
                    return "configured", "configured"
                elif 'unchanged' in output:
                    return "unchanged", "unchanged"
                else:
                    return "configured", "applied"
            else:
                return "error", result.stderr

        except Exception as e:
            kind = manifest.get('kind', 'Unknown')
            return "error", f"Failed to apply {kind}: {str(e)}"

    def rollout_restart(self, deployment: str, namespace: str) -> bool:
        """
        Restart a deployment by triggering a rollout.

        Args:
            deployment: Deployment name
            namespace: Namespace

        Returns:
            True if successful
        """
        try:
            apps_v1 = client.AppsV1Api(self._api_client)

            # Patch deployment with restart annotation
            now = client.ApiClient().datetime_to_str(client.ApiClient().now())
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": now
                            }
                        }
                    }
                }
            }

            apps_v1.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=body
            )
            return True

        except ApiException as e:
            print_warning(f"Failed to restart deployment {deployment}: {e.reason}")
            return False
