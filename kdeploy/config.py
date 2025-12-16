"""Configuration management for kdeploy."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

from kdeploy.utils import (
    ConfigError,
    deep_merge,
    get_env_var,
    find_ops_root,
)


class Config:
    """Configuration manager for kdeploy."""

    def __init__(self, config_path: Optional[Path] = None, environment: str = "test"):
        """
        Initialize configuration.

        Args:
            config_path: Path to kdeploy.yaml config file (can be string or Path)
            environment: Environment name (test, prod, etc.)
        """
        self.environment = environment
        # Convert string to Path if needed
        if config_path and not isinstance(config_path, Path):
            config_path = Path(config_path)
        self.config_path = config_path or self._find_config()
        self.root_dir = self.config_path.parent if self.config_path else Path.cwd()
        self._config: Dict[str, Any] = {}
        self._secrets: Dict[str, Any] = {}
        self._load_config()
        self._load_secrets()

    def _find_config(self) -> Optional[Path]:
        """Find kdeploy.yaml configuration file."""
        ops_root = find_ops_root()
        if ops_root:
            for name in ["kdeploy.yaml", "kdeploy.yml"]:
                config_file = ops_root / name
                if config_file.exists():
                    return config_file
        return None

    def _load_config(self) -> None:
        """Load configuration from kdeploy.yaml."""
        if not self.config_path or not self.config_path.exists():
            return

        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse config file: {e}")
        except IOError as e:
            raise ConfigError(f"Failed to read config file: {e}")

    def _load_secrets(self) -> None:
        """Load secrets from secrets file."""
        secrets_file = self.get("secrets_file", "secrets.yml")

        if not secrets_file:
            return

        secrets_path = Path(secrets_file)
        if not secrets_path.is_absolute():
            secrets_path = self.root_dir / secrets_path

        if not secrets_path.exists():
            # Secrets file is optional
            return

        try:
            with open(secrets_path, 'r') as f:
                self._secrets = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse secrets file: {e}")
        except IOError as e:
            raise ConfigError(f"Failed to read secrets file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_env_config(self, key: str, default: Any = None) -> Any:
        """
        Get environment-specific configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Try environment-specific config first
        env_value = self.get(f"environments.{self.environment}.{key}")
        if env_value is not None:
            return env_value

        # Fall back to global config
        return self.get(key, default)

    def get_secret(self, app_name: str, key: str, default: Any = None) -> Any:
        """
        Get secret value for an application.

        Args:
            app_name: Application name
            key: Secret key
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        app_secrets = self._secrets.get(app_name, {})
        return app_secrets.get(key, default)

    def get_global_secret(self, key: str, default: Any = None) -> Any:
        """
        Get global secret value.

        Args:
            key: Secret key
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        global_secrets = self._secrets.get("global", {})
        return global_secrets.get(key, default)

    def get_kubeconfig(self) -> Optional[str]:
        """Get kubeconfig path from config or environment."""
        kubeconfig = (
            get_env_var("KUBECONFIG") or
            self.get_env_config("kubeconfig") or
            self.get("kubeconfig")
        )
        return kubeconfig

    def get_namespace(self) -> Optional[str]:
        """Get namespace for current environment."""
        return self.get_env_config("namespace")

    def get_cluster_url(self) -> Optional[str]:
        """Get cluster URL for current environment."""
        return self.get_env_config("cluster_url")

    def get_apps_dir(self) -> Path:
        """Get applications directory path. Default: apps/"""
        apps_dir = self.get("apps_dir")
        if not apps_dir:
            apps_dir = "apps"

        apps_path = Path(apps_dir)

        if not apps_path.is_absolute():
            apps_path = self.root_dir / apps_path

        return apps_path

    def get_build_dir(self) -> Path:
        """Get build directory path. Default: build/"""
        build_dir = self.get("build_dir")
        if not build_dir:
            build_dir = "build"

        build_path = Path(build_dir)

        if not build_path.is_absolute():
            build_path = self.root_dir / build_path

        return build_path

    def list_apps(self) -> List[str]:
        """
        List available applications.

        Returns:
            List of application names
        """
        apps_dir = self.get_apps_dir()

        if not apps_dir.exists():
            return []

        apps = []
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            # Check if app has config.yml
            config_file = app_dir / "config.yml"
            if not config_file.exists():
                config_file = app_dir / "config.yaml"

            if config_file.exists():
                apps.append(app_dir.name)

        return sorted(apps)

    def get_app_config(self, app_name: str) -> Dict[str, Any]:
        """
        Get application-specific configuration.

        Args:
            app_name: Application name

        Returns:
            Application configuration dictionary
        """
        apps_dir = self.get_apps_dir()
        app_dir = apps_dir / app_name

        for config_name in ["config.yml", "config.yaml"]:
            config_file = app_dir / config_name
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        return yaml.safe_load(f) or {}
                except (yaml.YAMLError, IOError) as e:
                    raise ConfigError(f"Failed to load app config for {app_name}: {e}")

        return {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Get full configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self._config.copy()
