# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Configuration management utilities.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


class ConfigProvider:
    """
    Configuration provider with multiple backends.
    Supports loading configuration from YAML files and environment variables
    with clear separation of app settings, import settings, and runtime behavior.
    Environment variables take precedence over YAML settings.
    """

    @classmethod
    def get_section_mappings(cls) -> Dict[str, List[str]]:
        """
        Get the section mappings that define which configuration sections
        go into which internal storage dictionaries.

        This centralized mapping ensures consistency between different
        loading methods and makes it easy to add new configuration sections.

        Returns:
            Dict mapping target scope names to lists of section names
        """
        return {
            # APP SETTINGS - sections that go into app_settings
            "app_settings": [
                "nationbuilder",
                "nboauth",
                "oauth",
                "api",
                "frontend",
                "logos",
                "deployment",
            ],
            # RUNTIME SETTINGS - sections that go into runtime_settings
            "runtime_settings": ["runtime"],
            # STORAGE SETTINGS - sections that go into storage_settings
            "storage_settings": ["storage"],
            # LOGGING SETTINGS - sections that go into logging_settings
            "logging_settings": ["logging"],
        }

    def __init__(self, config_source: Optional[Union[str, Dict[str, Any]]] = None):
        """
        Initialize the config provider with distinct configuration scopes.

        Args:
            config_source: Path to a YAML configuration file or a configuration dictionary
        """
        # Initialize all configuration scopes
        self.app_settings = {}
        self.import_settings = {}
        self.runtime_settings = {}
        self.storage_settings = {}
        self.logging_settings = {}
        self.yaml_config = {}  # Ensure yaml_config is always initialized
        self.config_file_path = None  # Store original config file path for relative path resolution

        # Load from config source (YAML file or dictionary)
        if config_source:
            if isinstance(config_source, str):
                # File path
                if config_source.endswith(".yml") or config_source.endswith(".yaml"):
                    self.config_file_path = config_source  # Store for relative path resolution
                    self.load_from_yaml(config_source)

                    # OAuth configuration now handled via environment variables only
                else:
                    logger.warning(f"Unsupported configuration format: {config_source}")
            elif isinstance(config_source, dict):
                # Dictionary - Load directly into appropriate sections
                self.yaml_config = config_source
                self._load_from_dict(config_source)

        # Load from environment variables last (highest priority)
        self.load_from_env()

    def _load_from_dict(self, config_dict: Dict[str, Any]):
        """
        Load configuration from a dictionary into appropriate scopes.

        Args:
            config_dict: Configuration dictionary
        """
        logger.debug("Loading configuration from dictionary")
        logger.debug(f"Available config sections: {list(config_dict.keys())}")

        # Get section mappings from centralized definition
        section_mappings = self.get_section_mappings()

        # Process each section dynamically
        for target_scope, section_names in section_mappings.items():
            target_dict = getattr(self, target_scope)
            for section_name in section_names:
                if section_name in config_dict:
                    # Special handling for storage section - merge contents instead of nesting
                    if section_name == "storage" and target_scope == "storage_settings":
                        target_dict.update(config_dict[section_name])
                        logger.debug(
                            f"Merged section '{section_name}' contents into {target_scope}"
                        )
                    else:
                        target_dict[section_name] = config_dict[section_name]
                        logger.debug(f"Loaded section '{section_name}' into {target_scope}")

        # IMPORT SETTINGS - cli_import structure
        if "cli_import" in config_dict:
            cli_import = config_dict["cli_import"]

            # Store the complete cli_import configuration
            self.import_settings.update(cli_import)

            source_type = cli_import.get("type")
            input_file = cli_import.get("file")

            if source_type and input_file:
                logger.debug(
                    f"Loaded import settings from cli_import: type={source_type}, file={input_file}"
                )

            # Log additional cli_import settings
            if "job_cleanup" in cli_import:
                logger.debug(f"CLI job cleanup: {cli_import['job_cleanup']}")

        # DEPLOYMENT-AWARE PROCESSING - resolve "auto" values based on deployment type
        if "deployment" in config_dict:
            self._apply_deployment_aware_settings(config_dict)

    def load_from_env(self):
        """Load configuration from environment variables into appropriate scopes."""
        logger.debug("Loading configuration from environment variables")

        # APP SETTINGS
        if os.environ.get("NB_CONFIG_ENV"):
            self.app_settings["environment"] = os.environ.get("NB_CONFIG_ENV")

        # Load OAuth settings from environment if available
        self._load_oauth_from_env()
        self._setup_dynamic_oauth_config()

        # IMPORT SETTINGS
        if "IMPORT_SOURCE" in os.environ:
            source = os.environ.get("IMPORT_SOURCE", "").lower()
            input_file = os.environ.get("IMPORT_FILE", "")

            if source == "canadahelps" and input_file:
                self.import_settings["source_type"] = "canadahelps"
                self.import_settings["input_file"] = input_file
            elif source == "paypal" and input_file:
                self.import_settings["source_type"] = "paypal"
                self.import_settings["input_file"] = input_file

        # RUNTIME SETTINGS
        if "LOG_LEVEL" in os.environ:
            self.runtime_settings["log_level"] = os.environ.get("LOG_LEVEL")

        # STORAGE SETTINGS - Path configuration only
        # Local storage base path override
        base_path = os.environ.get("STORAGE_LOCAL_BASE_PATH")
        if base_path:
            if "default" not in self.storage_settings:
                self.storage_settings["default"] = {}
            self.storage_settings["default"]["base_path"] = base_path

        # LOGGING SETTINGS
        logging_provider = os.environ.get("LOGGING_PROVIDER")
        if logging_provider:
            if "provider" not in self.logging_settings:
                self.logging_settings["provider"] = logging_provider

        log_directory = os.environ.get("LOG_DIRECTORY")
        if log_directory:
            if "settings" not in self.logging_settings:
                self.logging_settings["settings"] = {}
            self.logging_settings["settings"]["directory"] = log_directory

        log_level = os.environ.get("LOG_LEVEL")
        if log_level:
            if "settings" not in self.logging_settings:
                self.logging_settings["settings"] = {}
            self.logging_settings["settings"]["level"] = log_level

        console_log_level = os.environ.get("CONSOLE_LOG_LEVEL")
        if console_log_level:
            if "settings" not in self.logging_settings:
                self.logging_settings["settings"] = {}
            self.logging_settings["settings"]["console_level"] = console_log_level

    def _load_oauth_from_env(self):
        """Load OAuth configuration from environment variables."""
        # Check if OAuth configuration is provided via environment variables
        oauth_vars_present = any(
            env_var in os.environ
            for env_var in [
                "NB_SLUG",
                "NB_CLIENT_ID",
                "NB_CLIENT_SECRET",
                "NB_REDIRECT_URI",
                "NB_CALLBACK_PORT",
            ]
        )

        if oauth_vars_present:
            # Ensure nationbuilder dict exists in app_settings
            if "nationbuilder" not in self.app_settings:
                self.app_settings["nationbuilder"] = {}

            # Always override with environment variables if present
            if os.environ.get("NB_SLUG"):
                self.app_settings["nationbuilder"]["slug"] = os.environ.get("NB_SLUG")
                logger.debug(f"Using NB_SLUG from environment: {os.environ.get('NB_SLUG')}")

            if os.environ.get("NB_CLIENT_ID"):
                self.app_settings["nationbuilder"]["client_id"] = os.environ.get("NB_CLIENT_ID")

            if os.environ.get("NB_CLIENT_SECRET"):
                self.app_settings["nationbuilder"]["client_secret"] = os.environ.get(
                    "NB_CLIENT_SECRET"
                )

            # Only set config_name if provided
            if os.environ.get("NB_CONFIG_NAME"):
                self.app_settings["nationbuilder"]["config_name"] = os.environ.get("NB_CONFIG_NAME")

            logger.debug("Loaded OAuth configuration from environment variables")

    def _setup_dynamic_oauth_config(self):
        """Setup dynamic OAuth configuration from frontend config."""
        logger.debug("Setting up dynamic OAuth configuration")

        # Ensure nationbuilder dict exists in app_settings
        if "nationbuilder" not in self.app_settings:
            self.app_settings["nationbuilder"] = {}

            # API CONFIGURATION
            if "api" not in self.app_settings:
                self.app_settings["api"] = {}

            # CORS Configuration
            cors_origins = os.environ.get("CORS_ORIGINS")
            if cors_origins:
                if "cors" not in self.app_settings["api"]:
                    self.app_settings["api"]["cors"] = {}
                self.app_settings["api"]["cors"]["origins"] = [
                    origin.strip() for origin in cors_origins.split(",")
                ]
                logger.debug(
                    f"Loaded CORS origins from environment: {self.app_settings['api']['cors']['origins']}"
                )

            # API Host/Port
            if os.environ.get("API_HOST"):
                self.app_settings["api"]["host"] = os.environ.get("API_HOST")
            if os.environ.get("API_PORT"):
                try:
                    self.app_settings["api"]["port"] = int(os.environ.get("API_PORT"))
                except ValueError:
                    logger.warning(f"Invalid API_PORT value: {os.environ.get('API_PORT')}")

            # LOGO CONFIGURATION
            if "logos" not in self.app_settings:
                self.app_settings["logos"] = {}

            if os.environ.get("LOGOS_USE_CUSTOM"):
                self.app_settings["logos"]["use_custom"] = (
                    os.environ.get("LOGOS_USE_CUSTOM").lower() == "true"
                )
            if os.environ.get("LOGOS_CUSTOM_PATH"):
                self.app_settings["logos"]["custom_path"] = os.environ.get("LOGOS_CUSTOM_PATH")
            if os.environ.get("LOGOS_FALLBACK_PATH"):
                self.app_settings["logos"]["fallback_path"] = os.environ.get("LOGOS_FALLBACK_PATH")

            # STORAGE PATH CONFIGURATION

            # LOGGING CONFIGURATION
            if "logging" not in self.logging_settings:
                self.logging_settings["logging"] = {}

            logging_provider = os.environ.get("LOGGING_PROVIDER")
            if logging_provider:
                self.logging_settings["logging"]["provider"] = logging_provider
                logger.debug(f"Set logging provider from environment: {logging_provider}")

            log_directory = os.environ.get("LOG_DIRECTORY")
            if log_directory:
                self.logging_settings["logging"]["directory"] = log_directory

            log_level = os.environ.get("LOG_LEVEL")
            if log_level:
                self.logging_settings["logging"]["level"] = log_level

            console_log_level = os.environ.get("CONSOLE_LOG_LEVEL")
            if console_log_level:
                self.logging_settings["logging"]["console_level"] = console_log_level

            # RUNTIME CONFIGURATION
            if "runtime" not in self.runtime_settings:
                self.runtime_settings["runtime"] = {}

            runtime_log_level = os.environ.get("RUNTIME_LOG_LEVEL")
            if runtime_log_level:
                self.runtime_settings["runtime"]["log_level"] = runtime_log_level

            job_worker_threads = os.environ.get("JOB_WORKER_THREADS")
            if job_worker_threads:
                try:
                    self.runtime_settings["runtime"]["job_worker_threads"] = int(job_worker_threads)
                except ValueError:
                    logger.warning(f"Invalid JOB_WORKER_THREADS value: {job_worker_threads}")

            # OAUTH EXTENSIONS
            nb_scope = os.environ.get("NB_SCOPE")
            if nb_scope:
                if "nationbuilder" not in self.app_settings:
                    self.app_settings["nationbuilder"] = {}
                self.app_settings["nationbuilder"]["scope"] = nb_scope

            # JWT Configuration
            jwt_expiration = os.environ.get("JWT_EXPIRATION")
            if jwt_expiration:
                try:
                    if "api" not in self.app_settings:
                        self.app_settings["api"] = {}
                    self.app_settings["api"]["jwt_expiration"] = int(jwt_expiration)
                except ValueError:
                    logger.warning(f"Invalid JWT_EXPIRATION value: {jwt_expiration}")

            refresh_expiration = os.environ.get("REFRESH_EXPIRATION")
            if refresh_expiration:
                try:
                    if "api" not in self.app_settings:
                        self.app_settings["api"] = {}
                    self.app_settings["api"]["refresh_expiration"] = int(refresh_expiration)
                except ValueError:
                    logger.warning(f"Invalid REFRESH_EXPIRATION value: {refresh_expiration}")

            logger.debug("Completed loading all configuration from environment variables")

    def resolve_config_relative_path(self, path: str) -> str:
        """
        Resolve a path relative to the config file location if it's not absolute.

        Args:
            path: Path that may be relative or absolute

        Returns:
            str: Resolved absolute path
        """
        from pathlib import Path

        path_obj = Path(path)
        if path_obj.is_absolute():
            return path

        # If we have a config file path and the path is relative, resolve against config directory
        if self.config_file_path:
            config_dir = Path(self.config_file_path).parent
            resolved_path = config_dir / path_obj
            return str(resolved_path)

        # Fallback to current working directory
        return path

    def get_config_directory(self) -> Optional[Path]:
        """Get the directory containing the config file."""
        if self.config_file_path:
            return Path(self.config_file_path).parent
        return None

    def load_from_yaml(self, path: str):
        """
        Load configuration from YAML file into appropriate scopes.

        Args:
            path (str): Path to the YAML configuration file
        """
        logger.debug(f"Loading configuration from YAML file: {path}")
        try:
            with open(path, "r") as file:
                yaml_config = yaml.safe_load(file)
                self.yaml_config = yaml_config  # This line was missing.

                if not yaml_config:
                    logger.error(f"Empty or invalid YAML configuration in {path}")
                    return

                # Parse and distribute settings to appropriate scopes using data-driven approach

                # Get section mappings from centralized definition
                section_mappings = self.get_section_mappings()

                # Process each section dynamically
                for target_scope, section_names in section_mappings.items():
                    target_dict = getattr(self, target_scope)
                    for section_name in section_names:
                        if section_name in yaml_config:
                            # Special handling for storage section - merge contents instead of nesting
                            if section_name == "storage" and target_scope == "storage_settings":
                                target_dict.update(yaml_config[section_name])
                                logger.debug(
                                    f"Merged section '{section_name}' contents into {target_scope}"
                                )
                            else:
                                target_dict[section_name] = yaml_config[section_name]
                                logger.debug(f"Loaded section '{section_name}' into {target_scope}")

                # IMPORT SETTINGS - special handling for source type detection
                # First check for new cli_import structure
                if "cli_import" in yaml_config:
                    cli_import = yaml_config["cli_import"]

                    # Store the complete cli_import configuration
                    self.import_settings.update(cli_import)

                    source_type = cli_import.get("type")
                    input_file = cli_import.get("file")

                    if source_type and input_file:
                        logger.debug(
                            f"Loaded import settings from cli_import: type={source_type}, file={input_file}"
                        )

                    # Log additional cli_import settings
                    if "job_cleanup" in cli_import:
                        logger.debug(f"CLI job cleanup: {cli_import['job_cleanup']}")
                # Fallback to old structure for backward compatibility
                elif "canadahelps" in yaml_config and yaml_config.get("canadahelps"):
                    input_file = yaml_config["canadahelps"].get("input_file")
                    if input_file:
                        self.import_settings["source_type"] = "canadahelps"
                        self.import_settings["input_file"] = input_file
                elif "paypal" in yaml_config and yaml_config.get("paypal"):
                    input_file = yaml_config["paypal"].get("input_file")
                    if input_file:
                        self.import_settings["source_type"] = "paypal"
                        self.import_settings["input_file"] = input_file

                # STORAGE SETTINGS - process storage configuration
                if "storage" in yaml_config:
                    pass  # Storage settings handled by parent class

                # DEPLOYMENT-AWARE PROCESSING - resolve "auto" values based on deployment type
                self._apply_deployment_aware_settings(yaml_config)

                logger.debug("Successfully loaded YAML configuration")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {path}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error loading YAML configuration: {str(e)}")

    def _apply_deployment_aware_settings(self, yaml_config: Dict[str, Any]):
        """
        Apply deployment-agnostic processing to resolve 'auto' values based on deployment patterns.
        Works with any hostname, port, or deployment scenario - makes no assumptions.
        """
        deployment_config = yaml_config.get("deployment", {})
        deployment_pattern = deployment_config.get("pattern", "local")
        user_hostname = deployment_config.get("hostname", "localhost")
        # The frontend_port is the primary, user-facing port for network modes.
        user_frontend_port = deployment_config.get("frontend_port", 8008)

        # Respect the user's api_port setting for all deployment modes
        user_api_port = deployment_config.get("api_port", 8000)

        logger.debug(
            f"Processing deployment-agnostic settings - pattern: {deployment_pattern}, hostname: {user_hostname}"
        )

        # Resolve API settings with 'auto' values
        if "api" in self.app_settings:
            api_config = self.app_settings["api"]

            # Resolve API host based on deployment pattern (not specific deployment)
            if api_config.get("host") == "auto":
                if deployment_pattern == "network":
                    api_config["host"] = "0.0.0.0"  # Bind to all interfaces for network access
                    logger.debug(f"Resolved API host to '0.0.0.0' for {deployment_pattern} pattern")
                else:  # local pattern
                    api_config["host"] = "localhost"
                    logger.debug("Resolved API host to 'localhost' for local pattern")

            # Use user-specified API port
            if api_config.get("port") == "auto":
                api_config["port"] = user_api_port
                logger.debug(f"Using user-specified API port: {user_api_port}")

        # Resolve Frontend settings with 'auto' values
        if "frontend" in self.app_settings:
            frontend_config = self.app_settings["frontend"]

            # Frontend host resolution - deployment pattern agnostic
            if frontend_config.get("host") == "auto":
                if deployment_pattern == "network":
                    frontend_config["host"] = "0.0.0.0"  # Network needs to bind to all
                    logger.debug("Resolved frontend host to '0.0.0.0' for network pattern")
                else:
                    # Use user-specified hostname for network/local patterns
                    frontend_config["host"] = user_hostname
                    logger.debug(
                        f"Resolved frontend host to '{user_hostname}' for {deployment_pattern} pattern"
                    )

            # Use user-specified frontend port
            if frontend_config.get("port") == "auto":
                frontend_config["port"] = user_frontend_port
                logger.debug(f"Using user-specified frontend port: {user_frontend_port}")

        # Generate CORS origins based on user configuration
        self._generate_cors_origins(deployment_config, user_hostname, user_api_port, user_frontend_port)

        # Load OAuth credentials and adjust for deployment
        self._load_oauth_credentials(deployment_config, user_hostname, user_frontend_port)

    def _detect_deployment_type(self) -> str:
        """
        Auto-detect deployment type based on environment variables and context.
        """
        # Check environment variable first
        env_deployment = os.environ.get("DEPLOYMENT_MODE", "").lower()
        if env_deployment in ["docker", "network", "local"]:
            return env_deployment

        # Check for Docker environment
        if os.path.exists("/.dockerenv") or os.environ.get("KUBERNETES_SERVICE_HOST"):
            return "docker"

        # Check for network deployment indicators
        hostname = os.environ.get("HOSTNAME", "")
        if hostname.endswith(".lan") or hostname.startswith("rpi-"):
            return "network"

        # Default to local
        return "local"

    def _generate_cors_origins(
        self, deployment_config: Dict[str, Any], user_hostname: str, user_api_port: int, user_frontend_port: int
    ):
        """
        Generate CORS origins based on user-specified deployment configuration.
        This version supports hostnames, IP addresses, CIDR ranges, and wildcards.
        """
        if "api" not in self.app_settings:
            self.app_settings["api"] = {}

        api_config = self.app_settings["api"]
        cors_config = api_config.setdefault("cors", {})

        if "origins" in cors_config and cors_config["origins"]:
            logger.debug("CORS origins manually specified, skipping auto-generation")
            return

        origins_patterns = []
        # Always add the primary hostname for the application itself
        origins_patterns.append(f"http://{user_hostname}:{user_frontend_port}")
        # Also add API port for same-origin requests to API
        origins_patterns.append(f"http://{user_hostname}:{user_api_port}")

        additional_origins = deployment_config.get("additional_origins", [])
        for origin in additional_origins:
            # Check for CIDR notation first
            if "/" in origin and all(
                part.isdigit() or part == "." for part in origin.split("/")[0].split(".")
            ):
                try:
                    import ipaddress

                    net = ipaddress.ip_network(origin, strict=False)
                    # Create a regex to match any IP in the subnet
                    # This is a simplified regex for private networks
                    network_prefix = str(net.network_address).rsplit(".", 1)[0]
                    pattern = network_prefix.replace(".", r"\.") + r"\.\d{1,3}"
                    origins_patterns.append(f"^https?://{pattern}:{user_frontend_port}$")
                    origins_patterns.append(f"^https?://{pattern}:{user_api_port}$")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid CIDR notation in additional_origins: '{origin}'")
            elif "*" in origin:
                # Handle wildcard domains like *.work.lan
                pattern = origin.replace(".", r"\.").replace("*", "[a-zA-Z0-9-]+")
                origins_patterns.append(f"^https?://{pattern}:{user_frontend_port}$")
                origins_patterns.append(f"^https?://{pattern}:{user_api_port}$")
            else:
                # Handle standard hostnames, IPs, and full URLs
                # Add both frontend and API ports for this origin
                if origin.startswith("http"):
                    origins_patterns.append(origin)
                else:
                    origins_patterns.append(f"http://{origin}:{user_frontend_port}")
                    origins_patterns.append(f"http://{origin}:{user_api_port}")

        # Add common localhost variants if not already the primary
        if user_hostname != "localhost":
            origins_patterns.extend(
                [f"http://localhost:{user_frontend_port}", f"http://127.0.0.1:{user_frontend_port}", f"http://localhost:{user_api_port}", f"http://127.0.0.1:{user_api_port}"]
            )

        cors_config["origins"] = list(set(origins_patterns))
        logger.debug(f"Generated CORS origins/patterns: {cors_config['origins']}")

    def _load_oauth_credentials(
        self, deployment_config: Dict[str, Any], user_hostname: str, user_frontend_port: int
    ):
        """
        OAuth credentials are now loaded exclusively from environment variables.
        This method is kept for backward compatibility but does nothing.
        """
        logger.debug("OAuth credentials loaded from environment variables only")

    def _adjust_oauth_for_deployment(self, deployment_config: Dict[str, Any], deployment_type: str):
        """
        Adjust OAuth configuration based on deployment type.
        """
        # This will be handled by the existing dynamic OAuth system
        # Just log that deployment-aware OAuth processing is available
        logger.debug(f"OAuth configuration will be adjusted for {deployment_type} deployment")



    def detect_deployment_mode(self) -> str:
        """
        Detect the deployment mode based on environment and network context.

        Returns:
            str: 'localhost' for local deployment, 'network_access' for network deployment
        """
        # Method 1: Check environment variable override
        deployment_mode = os.environ.get("DEPLOYMENT_MODE")
        if deployment_mode:
            logger.debug(f"Using deployment mode from environment: {deployment_mode}")
            return deployment_mode

        # Method 2: Check for common network environment indicators
        # If APP_BASE_URL is set and contains non-localhost hostname, assume network deployment
        app_base_url = os.environ.get("APP_BASE_URL")
        if app_base_url:
            from urllib.parse import urlparse

            try:
                parsed = urlparse(app_base_url)
                hostname = parsed.hostname
                if hostname and hostname not in ["localhost", "127.0.0.1"]:
                    logger.debug(
                        f"Network deployment detected from APP_BASE_URL hostname: {hostname}"
                    )
                    return "network_access"
            except Exception as e:
                logger.warning(f"Failed to parse APP_BASE_URL for deployment detection: {e}")

        # Method 3: Check hostname patterns from potential request context
        # This will be enhanced when we have request context available

        # Default to localhost deployment
        logger.debug("Defaulting to localhost deployment mode")
        return "localhost"

    def detect_deployment_mode_from_request(self, request_host: str) -> str:
        """
        Detect deployment mode based on the actual request host.
        This provides more accurate detection than environment-based detection.

        Args:
            request_host: The Host header from the HTTP request

        Returns:
            str: 'localhost' for local deployment, 'network_access' for network deployment
        """
        if not request_host:
            return self.detect_deployment_mode()

        # Parse the host (may include port)
        host_parts = request_host.split(":")
        hostname = host_parts[0] if host_parts else request_host

        # Check for localhost patterns
        localhost_patterns = ["localhost", "127.0.0.1"]
        if hostname in localhost_patterns:
            logger.debug(f"Localhost deployment detected from request host: {request_host}")
            return "localhost"

        # Check for network access patterns
        network_patterns = [
            lambda h: h.endswith(".work.lan"),  # .work.lan domain
            lambda h: h.startswith("rpi-"),  # rpi-* hostnames
            lambda h: h.count(".") == 3 and all(p.isdigit() for p in h.split(".")),  # IP addresses
        ]

        for pattern in network_patterns:
            try:
                if pattern(hostname):
                    logger.debug(f"Network deployment detected from request host: {request_host}")
                    return "network_access"
            except Exception:
                continue

        # Default to network access for unrecognized patterns (safer for OAuth)
        logger.debug(f"Unknown request host pattern '{request_host}', defaulting to network_access")
        return "network_access"


    def get_oauth_config(self):
        """
        Get the complete OAuth configuration.

        Returns:
            dict: The OAuth configuration for NationBuilder
        """
        from .secure_config import SecureConfigValidator
        
        # Use environment variables for OAuth configuration
        try:
            oauth_config = SecureConfigValidator.get_oauth_config()
            
            # Auto-generate redirect_uri if not provided
            if "redirect_uri" not in oauth_config or not oauth_config["redirect_uri"]:
                deployment_config = self.yaml_config.get("deployment", {})
                user_hostname = deployment_config.get("hostname", "localhost")
                user_api_port = deployment_config.get("api_port", 8000)
                
                callback_url = f"http://{user_hostname}:{user_api_port}/callback"
                oauth_config["redirect_uri"] = callback_url
                oauth_config["callback_port"] = user_api_port
                
                logger.debug(f"Auto-generated OAuth redirect_uri: {callback_url}")
            
            return oauth_config
            
        except ValueError as e:
            logger.error(f"OAuth environment variable validation failed: {e}")
            raise ValueError(f"OAuth configuration required: {e}")

    def get_api_config(self):
        """
        Get the complete API configuration including ports and URLs.

        Returns:
            dict: The API configuration with port, host, cors, etc.
        """
        return self.app_settings.get("api", {})

    def get_api_base_url(self, request_host: Optional[str] = None) -> str:
        """
        Generate the public-facing API base URL for frontend clients.
        This must use the public hostname, not the internal bind address.
        If request_host is provided, it will be used to construct the base URL.
        """
        # The port is correctly resolved from the deployment settings already.
        api_config = self.get_api_config()
        port = api_config.get("port", 8000)

        # If a request_host is provided, use it to construct the base URL
        if request_host:
            # Check if the request_host includes a port
            if ":" in request_host:
                public_hostname, _ = request_host.split(":", 1)
            else:
                public_hostname = request_host

            # Return full URL with hostname and port
            return f"http://{public_hostname}:{port}"

        # The public hostname must come from the deployment section.
        deployment_config = self.yaml_config.get("deployment", {})
        public_hostname = deployment_config.get("hostname", "localhost")

        return f"http://{public_hostname}:{port}"

    def get_frontend_config(self):
        """
        Get the complete frontend configuration including ports and URLs.

        Returns:
            dict: The frontend configuration with port, host, etc.
        """
        return self.app_settings.get("frontend", {})

    def get_frontend_base_url(self):
        """
        Generate frontend base URL from host and port configuration.

        Returns:
            str: The frontend base URL (e.g., "http://localhost:8001")
        """
        frontend_config = self.get_frontend_config()
        host = frontend_config.get("host", "localhost")
        port = frontend_config.get("port", 8008)
        return f"http://{host}:{port}"

    def get_storage_config(self):
        """
        Get the complete storage configuration.

        Returns:
            dict: The storage configuration
        """
        return self.storage_settings

    def get_provider_config_by_name(self, provider_name: str) -> Dict[str, Any]:
        """
        Get a provider configuration by name.

        This is useful for getting a specific provider configuration directly,
        without going through the file type or route resolution process.

        Args:
            provider_name: Name of the provider (e.g., 'local', 's3')

        Returns:
            dict: Provider configuration with the specified name

        Raises:
            ValueError: If no provider with the specified name is found
        """
        # First check for provider defaults
        provider_defaults = self.get_provider_defaults()
        if provider_defaults.get("type") == provider_name:
            return provider_defaults

        # Check the default provider
        if (
            "default" in self.storage_settings
            and self.storage_settings["default"].get("type") == provider_name
        ):
            return self.storage_settings["default"]

        # No provider found, raise an error
        raise ValueError(f"No provider configuration found with name '{provider_name}'")

    def validate_storage_config(self) -> bool:
        """
        Validate the storage configuration.

        This checks for common issues in the storage configuration and logs warnings.

        Returns:
            bool: True if the configuration is valid, False if there are errors
        """
        valid = True

        # Check if we have paths configuration
        if "paths" not in self.storage_settings:
            logger.warning("Storage configuration missing paths section")
            valid = False

        return valid

    def get_logging_config(self):
        """
        Get the complete logging configuration.

        Returns:
            dict: The logging configuration
        """
        return self.logging_settings

    def get_app_setting(self, path: List[str] = None, default: Any = None) -> Any:
        """
        Get an application-wide setting - NO DEFAULTS ALLOWED (unless explicitly requested).

        Args:
            path: List of keys to navigate through nested dictionaries
            default: Default value to return if path is not found (use sparingly)

        Returns:
            Setting value or None if not found (unless default provided)
        """
        if path is None:
            return self.app_settings

        current = self.app_settings
        # Check app_settings first
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                # If not found in app_settings, and path starts with 'deployment', check yaml_config
                if path[0] == "deployment":
                    current = self.yaml_config
                    for deploy_key in path:
                        if isinstance(current, dict) and deploy_key in current:
                            current = current[deploy_key]
                        else:
                            if default is None:
                                logger.warning(
                                    f"Config path {'.'.join(path)} not found in yaml_config and no default provided"
                                )
                            return default

                if default is None:
                    logger.warning(
                        f"Config path {'.'.join(path)} not found and no default provided"
                    )
                return default
        return current

    def get_import_setting(self, key: str = None, default: Any = None) -> Any:
        """
        Get an import-specific setting.

        Args:
            key: Setting key or None to get all import settings
            default: Default value to return if key is not found

        Returns:
            Setting value or default
        """
        if key is None:
            return self.import_settings
        return self.import_settings.get(key, default)

    def get_runtime_setting(self, key: str = None, default: Any = None) -> Any:
        """
        Get a runtime behavior setting.

        Args:
            key: Setting key or None to get all runtime settings
            default: Default value to return if key is not found

        Returns:
            Setting value or default
        """
        if key is None:
            return self.runtime_settings
        return self.runtime_settings.get(key, default)

    def update_runtime_setting(self, key: str, value: Any) -> None:
        """
        Update a runtime behavior setting.

        Args:
            key: Setting key
            value: New setting value
        """
        self.runtime_settings[key] = value
        logger.debug(f"Updated runtime setting: {key} = {value}")

    def get_cleanup_config(self, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get file cleanup configuration settings.

        Args:
            default: Default configuration to return if not found

        Returns:
            Dict containing cleanup configuration
        """
        if default is None:
            default = {
                "enabled": True,  # Enable cleanup by default
                "tool": "uneff",  # Default cleanup tool
                "fallback_on_error": True,  # Continue processing if cleanup fails
                "log_changes": True,  # Log when files are cleaned
                "timeout": 30,  # Cleanup operation timeout in seconds
            }

        # Check for cleanup config in various locations
        cleanup_config = None

        # First check processing.cleanup
        processing_config = self.get_runtime_setting("processing", {})
        if isinstance(processing_config, dict) and "cleanup" in processing_config:
            cleanup_config = processing_config["cleanup"]

        # Fallback to direct cleanup section
        if cleanup_config is None:
            cleanup_config = self.get_runtime_setting("cleanup", {})

        # If still no config, check yaml_config directly
        if not cleanup_config and hasattr(self, "yaml_config"):
            cleanup_config = self.yaml_config.get("cleanup", {})
            if not cleanup_config:
                processing = self.yaml_config.get("processing", {})
                if isinstance(processing, dict):
                    cleanup_config = processing.get("cleanup", {})

        # Merge with defaults
        final_config = default.copy()
        if isinstance(cleanup_config, dict):
            final_config.update(cleanup_config)

        return final_config

    def is_cleanup_enabled(self) -> bool:
        """
        Check if file cleanup is enabled.

        Returns:
            bool: True if cleanup is enabled, False otherwise
        """
        cleanup_config = self.get_cleanup_config()
        return cleanup_config.get("enabled", True)

    # New methods for handling file type-based storage configuration

    def normalize_provider_config(self, provider_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a provider configuration by ensuring it has all required fields.

        Args:
            provider_config: Provider configuration to normalize

        Returns:
            Dict: Normalized provider configuration with all required fields
        """
        if not provider_config:
            # Empty config, return a default local provider
            return {"type": "local"}

        # Create a copy to avoid modifying the original
        normalized = provider_config.copy()

        # Ensure the provider has a type
        if "type" not in normalized:
            # Try to get the type from defaults
            defaults = self.get_provider_defaults()
            if "type" in defaults:
                normalized["type"] = defaults["type"]
            else:
                # Fall back to local provider
                normalized["type"] = "local"
                logger.warning("No provider type specified, defaulting to 'local'")

        # Validate the provider type (only local is fully supported for now)
        valid_types = ["local"]  # Add 's3', etc. as they're implemented
        if normalized["type"] not in valid_types:
            logger.warning(
                f"Unsupported provider type '{normalized['type']}', defaulting to 'local'"
            )
            normalized["type"] = "local"

        return normalized

    def get_provider_defaults(self) -> Dict[str, Any]:
        """
        Get the provider defaults configuration.

        Returns:
            Dict: The provider defaults configuration
        """
        # Get provider defaults from new-style configuration
        provider_defaults = self.storage_settings.get("provider_defaults", {})

        # If no provider defaults but there's a default provider, use that as defaults
        if not provider_defaults and "default" in self.storage_settings:
            provider_defaults = self.storage_settings["default"].copy()

        # Ensure defaults include a type
        if "type" not in provider_defaults:
            provider_defaults["type"] = "local"
            logger.debug("No provider type in defaults, using 'local'")

        return provider_defaults

    # === NEW PATHS SYSTEM COMPATIBILITY ===

    def has_simple_paths_config(self) -> bool:
        """
        Check if the configuration uses the new simple paths format.

        Returns:
            bool: True if simple paths format is used
        """
        return "paths" in self.storage_settings

    def get_simple_paths_config(self) -> Optional[Dict[str, str]]:
        """
        Get the simple paths configuration.

        Returns:
            Dict or None: The simple paths configuration, or None if not present
        """
        return self.storage_settings.get("paths")

    def add_simple_paths_config(self, paths: Dict[str, str]) -> None:
        """
        Add simple paths configuration to storage settings.

        Args:
            paths: Dictionary of path mappings
        """
        self.storage_settings["paths"] = paths
        logger.debug(f"Added simple paths configuration: {paths}")

    def get_effective_storage_config(self) -> Dict[str, Any]:
        """
        Get the effective storage configuration using simple paths format.

        Returns:
            Dict: Storage configuration with paths resolved
        """
        return self.storage_settings.copy()
