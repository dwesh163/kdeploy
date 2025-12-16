# kdeploy

**kdeploy** is an extensible Kubernetes deployment CLI tool inspired by Ansible. It provides a modern, Python-based approach to managing Kubernetes deployments with multi-environment support, powerful template rendering, and a plugin system for extensibility.

## Features

- **Multi-Environment Support**: Easily deploy to test, staging, production, or custom environments
- **Multi-Namespace Support**: Deploy applications across different Kubernetes namespaces
- **Template Rendering**: Powerful Jinja2-based template system with custom filters
- **Component-Based Architecture**: Organize applications into logical components (backend, frontend, database, etc.)
- **Dry-Run Mode**: Test deployments without applying changes
- **Extensible Plugin System**: Add custom functionality via plugins
- **Rich CLI Output**: Beautiful, colored terminal output using Rich
- **Secrets Management**: Separate secrets file for sensitive configuration
- **Kubernetes Native**: Built on the official Kubernetes Python client

## Installation

### From Source

```bash
git clone https://github.com/dwesh163/kdeploy.git
cd kdeploy
pip install -e .
```

### Using pip (when published)

```bash
pip install kdeploy
```

## Quick Start

### 1. Initialize Your Project

Create a directory structure for your ops configuration:

```
my-ops/
├── kdeploy.yaml         # Main configuration file
├── secrets.yml          # Secrets (do not commit!)
├── apps/                # Applications directory
│   └── myapp/
│       ├── config.yml
│       ├── backend/
│       │   ├── config.yml
│       │   └── templates/
│       │       ├── deployment.yml
│       │       └── service.yml
│       └── frontend/
│           ├── config.yml
│           └── templates/
│               ├── deployment.yml
│               ├── service.yml
│               └── ingress.yml
└── plugins/             # Custom plugins (optional)
```

### 2. Configure kdeploy.yaml

```yaml
# kdeploy.yaml
secrets_file: secrets.yml
kubeconfig: /path/to/kubeconfig.yml

apps_dir: apps
build_dir: build

environments:
  test:
    namespace: myapp-test
  prod:
    namespace: myapp-prod

global:
  organization: "My Organization"
```

### 3. Create secrets.yml

```yaml
# secrets.yml (add to .gitignore!)
global:
  registry_password: mypassword

myapp:
  database_password: supersecret
  api_key: abcdef123456
```

### 4. Deploy Your Application

```bash
# List available applications
kdeploy list

# Build templates for an application
kdeploy build myapp --env test

# Deploy to test environment
kdeploy deploy myapp --env test

# Deploy to production with dry-run
kdeploy deploy myapp --env prod --dry-run

# Deploy all applications
kdeploy deploy --all --env test

# Check cluster status
kdeploy status --env test
```

## Usage

### Commands

#### `kdeploy build <app> [options]`

Build (render) application templates without deploying.

**Options:**
- `--env, -e`: Environment name (default: test)
- `--config, -c`: Path to kdeploy.yaml

**Example:**
```bash
kdeploy build myapp --env prod
```

#### `kdeploy deploy [app] [options]`

Deploy application(s) to Kubernetes.

**Options:**
- `--env, -e`: Environment name (default: test)
- `--namespace, -n`: Override namespace
- `--dry-run`: Simulate deployment without applying
- `--all`: Deploy all applications
- `--skip-build`: Skip build step (use existing build)
- `--config, -c`: Path to kdeploy.yaml

**Examples:**
```bash
# Deploy single app
kdeploy deploy myapp --env prod

# Deploy all apps with dry-run
kdeploy deploy --all --env prod --dry-run

# Deploy to specific namespace
kdeploy deploy myapp --env test --namespace custom-ns
```

#### `kdeploy list [options]`

List available applications.

**Options:**
- `--env, -e`: Environment name (default: test)
- `--config, -c`: Path to kdeploy.yaml

**Example:**
```bash
kdeploy list
```

#### `kdeploy status [options]`

Show cluster and deployment status.

**Options:**
- `--env, -e`: Environment name (default: test)
- `--namespace, -n`: Override namespace
- `--app, -a`: Filter by application name
- `--config, -c`: Path to kdeploy.yaml

**Example:**
```bash
kdeploy status --env prod --app myapp
```

## Template System

kdeploy uses Jinja2 for template rendering with custom filters and variables.

### Available Variables

Templates have access to the following variables:

- `{{ app.name }}`: Application name
- `{{ app.version }}`: Application version
- `{{ env }}`: Current environment (test, prod, etc.)
- `{{ namespace }}`: Kubernetes namespace
- `{{ config.* }}`: App-level configuration from config.yml
- `{{ component.* }}`: Component-level configuration
- `{{ secret.* }}`: Application secrets
- `{{ global.* }}`: Global secrets

### Custom Filters

- `{{ value | b64encode }}`: Base64 encode a value
- `{{ value | b64decode }}`: Base64 decode a value

### Template Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ app.name }}-backend
  namespace: {{ namespace }}
  labels:
    app: {{ app.name }}
    environment: {{ env }}
spec:
  replicas: {{ component.resources[env].replicas }}
  template:
    spec:
      containers:
      - name: backend
        image: {{ config.image.registry }}/{{ app.name }}:{{ app.version }}
        env:
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ app.name }}-secrets
              key: database-password
        resources:
          requests:
            cpu: {{ component.resources[env].cpu_request }}
            memory: {{ component.resources[env].memory_request }}
```

## Configuration Files

### kdeploy.yaml

Main configuration file for kdeploy.

```yaml
# Path to secrets file
secrets_file: secrets.yml

# Kubeconfig path (can be overridden by KUBECONFIG env var)
kubeconfig: /path/to/kubeconfig.yml

# Directories
apps_dir: apps
build_dir: build

# Environment configurations
environments:
  test:
    namespace: myapp-test
    cluster_url: https://api.test.k8s.example.com:6443  # Optional

  prod:
    namespace: myapp-prod

# Global variables
global:
  organization: "My Org"
```

### App config.yml

Application-level configuration.

```yaml
app:
  name: myapp
  version: "1.0.0"

domain:
  test: myapp-test.example.com
  prod: myapp.example.com

image:
  registry: docker.io/myorg
  pull_policy: Always
```

### Component config.yml

Component-level configuration.

```yaml
resources:
  test:
    replicas: 2
    cpu_request: "100m"
    memory_request: "256Mi"

  prod:
    replicas: 3
    cpu_request: "200m"
    memory_request: "512Mi"

port: 8080
health_check_path: /health
```

## Plugin System

kdeploy supports plugins to extend functionality.

### Creating a Plugin

Create a Python file in the `plugins/` directory:

```python
# plugins/my_plugin.py
from kdeploy.plugins import hookimpl

class MyPlugin:
    @hookimpl
    def kdeploy_pre_deploy(self, app_name, config, namespace):
        """Called before deploying an application."""
        print(f"Pre-deploy hook: {app_name}")

    @hookimpl
    def kdeploy_post_deploy(self, app_name, config, namespace, success, stats):
        """Called after deploying an application."""
        if success:
            print(f"Post-deploy hook: {app_name} deployed successfully!")

    @hookimpl
    def kdeploy_template_filters(self):
        """Add custom Jinja2 filters."""
        def uppercase(text):
            return text.upper()

        return {"uppercase": uppercase}

def register():
    """Register plugin with kdeploy."""
    return MyPlugin()
```

### Available Hooks

- `kdeploy_pre_build(app_name, config)`: Called before building
- `kdeploy_post_build(app_name, config, template_count)`: Called after building
- `kdeploy_pre_deploy(app_name, config, namespace)`: Called before deploying
- `kdeploy_post_deploy(app_name, config, namespace, success, stats)`: Called after deploying
- `kdeploy_template_filters()`: Add custom template filters
- `kdeploy_add_commands()`: Add custom CLI commands

## Environment Variables

- `KUBECONFIG`: Override kubeconfig file path
- `SECRETS_FILE`: Override secrets file path

## Development

### Setup Development Environment

```bash
git clone https://github.com/dwesh163/kdeploy.git
cd kdeploy
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black kdeploy/
```

## Examples

Complete examples are available in the `examples/` directory:

- `examples/kdeploy.yaml`: Example configuration
- `examples/secrets.yml`: Example secrets file
- `examples/apps/myapp/`: Example application with frontend and backend components

## Comparison with Other Tools

### vs Bash Scripts (kooked-ch/ops, sidoc.ops)

- **Maintainability**: Python is easier to maintain and test than complex Bash scripts
- **Extensibility**: Plugin system allows easy customization without modifying core code
- **Error Handling**: Better error handling and user feedback
- **IDE Support**: Better IDE support, type hints, and code completion

### vs Helm

- **Simplicity**: No Helm-specific concepts to learn
- **Flexibility**: Full power of Jinja2 templates
- **Integration**: Easy to integrate with existing CI/CD pipelines
- **Component-Based**: Natural organization by components

### vs Ansible

- **Kubernetes-Native**: Built specifically for Kubernetes
- **Lightweight**: No need for inventory files or complex playbooks
- **Fast**: Direct Kubernetes API communication
- **Modern**: Rich CLI output and modern Python practices

## Roadmap

- [ ] Add support for Kustomize overlays
- [ ] Implement rollback functionality
- [ ] Add diff view before deployment
- [ ] Support for Helm charts integration
- [ ] Web UI for deployment management
- [ ] GitOps integration
- [ ] Multi-cluster support
- [ ] Deployment history and audit logs

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Credits

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Jinja2](https://jinja.palletsprojects.com/) - Template engine
- [Kubernetes Python Client](https://github.com/kubernetes-client/python) - Kubernetes API client
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Pluggy](https://pluggy.readthedocs.io/) - Plugin system
