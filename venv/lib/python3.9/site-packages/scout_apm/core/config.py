# coding=utf-8

import logging
import os
import re
import warnings
from typing import Any, Dict, List, Optional, Union

from scout_apm.core import platform_detection

logger = logging.getLogger(__name__)

key_regex = re.compile(r"[a-zA-Z0-9]{16}")


class ScoutConfig(object):
    """
    Configuration object for the ScoutApm agent.

    Contains a list of configuration "layers". When a configuration key is
    looked up, each layer is asked in turn if it knows the value. The first one
    to answer affirmatively returns the value.
    """

    def __init__(self):
        self.layers = [
            Env(),
            Python(),
            Derived(self),
            Defaults(),
            Null(),
        ]

    def value(self, key: str) -> Any:
        value = self.locate_layer_for_key(key).value(key)
        if key in CONVERSIONS:
            return CONVERSIONS[key](value)
        return value

    def locate_layer_for_key(self, key: str) -> Any:
        for layer in self.layers:
            if layer.has_config(key):
                return layer

        # Should be unreachable because Null returns None for all keys.
        raise ValueError("key {!r} not found in any layer".format(key))

    def log(self) -> None:
        logger.debug("Configuration Loaded:")
        for key in self.known_keys:
            if key in self.secret_keys:
                continue

            layer = self.locate_layer_for_key(key)
            logger.debug(
                "%-9s: %s = %s",
                layer.__class__.__name__,
                key,
                layer.value(key),
            )

    known_keys = [
        "app_server",
        "application_root",
        "collect_remote_ip",
        "core_agent_config_file",
        "core_agent_dir",
        "core_agent_download",
        "core_agent_launch",
        "core_agent_log_file",
        "core_agent_log_level",
        "core_agent_permissions",
        "core_agent_socket_path",
        "core_agent_version",
        "disabled_instruments",
        "download_url",
        "framework",
        "framework_version",
        "hostname",
        "ignore",  # Deprecated in favor of ignore_endpoints
        "ignore_endpoints",
        "ignore_jobs",
        "key",
        "log_level",
        "log_payload_content",
        "monitor",
        "name",
        "revision_sha",
        "sample_rate",
        "endpoint_sample_rate",
        "sample_endpoints",
        "sample_jobs",
        "job_sample_rate",
        "scm_subdirectory",
        "shutdown_message_enabled",
        "shutdown_timeout_seconds",
    ]

    secret_keys = {"key"}

    def core_agent_permissions(self) -> int:
        try:
            return int(str(self.value("core_agent_permissions")), 8)
        except ValueError:
            logger.exception(
                "Invalid core_agent_permissions value, using default of 0o700"
            )
            return 0o700

    @classmethod
    def set(cls, **kwargs: Any) -> None:
        """
        Sets a configuration value for the Scout agent. Values set here will
        not override values set in ENV.
        """
        for key, value in kwargs.items():
            SCOUT_PYTHON_VALUES[key] = value

    @classmethod
    def unset(cls, *keys: str) -> None:
        """
        Removes a configuration value for the Scout agent.
        """
        for key in keys:
            SCOUT_PYTHON_VALUES.pop(key, None)

    @classmethod
    def reset_all(cls) -> None:
        """
        Remove all configuration settings set via `ScoutConfig.set(...)`.

        This is meant for use in testing.
        """
        SCOUT_PYTHON_VALUES.clear()


# Module-level data, the ScoutConfig.set(key="value") adds to this
SCOUT_PYTHON_VALUES = {}


class Python(object):
    """
    A configuration overlay that lets other parts of python set values.
    """

    def has_config(self, key: str) -> bool:
        return key in SCOUT_PYTHON_VALUES

    def value(self, key: str) -> Any:
        return SCOUT_PYTHON_VALUES[key]


class Env(object):
    """
    Reads configuration from environment by prefixing the key
    requested with "SCOUT_"

    Example: the `key` config looks for SCOUT_KEY
    environment variable
    """

    def has_config(self, key: str) -> bool:
        env_key = self.modify_key(key)
        return env_key in os.environ

    def value(self, key: str) -> Any:
        env_key = self.modify_key(key)
        return os.environ[env_key]

    def modify_key(self, key: str) -> str:
        env_key = ("SCOUT_" + key).upper()
        return env_key


class Derived(object):
    """
    A configuration overlay that calculates from other values.
    """

    def __init__(self, config: ScoutConfig):
        """
        config argument is the overall ScoutConfig var, so we can lookup the
        components of the derived info.
        """
        self.config = config

    def has_config(self, key: str) -> bool:
        return self.lookup_func(key) is not None

    def value(self, key: str) -> Any:
        return self.lookup_func(key)()

    def lookup_func(self, key: str) -> Optional[Any]:
        """
        Returns the derive_#{key} function, or None if it isn't defined
        """
        func_name = "derive_" + key
        return getattr(self, func_name, None)

    def derive_core_agent_full_name(self) -> str:
        triple = self.config.value("core_agent_triple")
        if not platform_detection.is_valid_triple(triple):
            warnings.warn(
                "Invalid value for core_agent_triple: {}".format(triple), stacklevel=2
            )
        return "{name}-{version}-{triple}".format(
            name="scout_apm_core",
            version=self.config.value("core_agent_version"),
            triple=triple,
        )

    def derive_core_agent_triple(self) -> str:
        return platform_detection.get_triple()


class Defaults(object):
    """
    Provides default values for important configurations
    """

    def __init__(self):
        self.defaults = {
            "app_server": "",
            "application_root": os.getcwd(),
            "collect_remote_ip": True,
            "core_agent_dir": "/tmp/scout_apm_core",
            "core_agent_download": True,
            "core_agent_launch": True,
            "core_agent_log_level": "info",
            "core_agent_permissions": 700,
            "core_agent_socket_path": "tcp://127.0.0.1:6590",
            "core_agent_version": "v1.5.0",  # can be an exact tag name, or 'latest'
            "disabled_instruments": [],
            "download_url": (
                "https://s3-us-west-1.amazonaws.com/scout-public-downloads/"
                "apm_core_agent/release"
            ),  # noqa: B950
            "errors_batch_size": 5,
            "errors_enabled": True,
            "errors_ignored_exceptions": (),
            "errors_host": "https://errors.scoutapm.com",
            "framework": "",
            "framework_version": "",
            "hostname": None,
            "ignore": [],
            "ignore_endpoints": [],
            "ignore_jobs": [],
            "key": "",
            "log_payload_content": False,
            "monitor": False,
            "name": "Python App",
            "revision_sha": self._git_revision_sha(),
            "sample_rate": 100,
            "sample_endpoints": [],
            "endpoint_sample_rate": None,
            "sample_jobs": [],
            "job_sample_rate": None,
            "scm_subdirectory": "",
            "shutdown_message_enabled": True,
            "shutdown_timeout_seconds": 2.0,
            "uri_reporting": "filtered_params",
        }

    def _git_revision_sha(self) -> str:
        # N.B. The environment variable SCOUT_REVISION_SHA may also be used,
        # but that will be picked up by Env
        return os.environ.get("HEROKU_SLUG_COMMIT", "")

    def has_config(self, key: str) -> bool:
        return key in self.defaults

    def value(self, key: str) -> Any:
        return self.defaults[key]


class Null(object):
    """
    Always answers that a key is present, but the value is None

    Used as the last step of the layered configuration.
    """

    def has_config(self, key: str) -> bool:
        return True

    def value(self, key: str) -> None:
        return None


def _strip_leading_slash(path: str) -> str:
    return path.lstrip(" /").strip()


def convert_to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("yes", "true", "t", "1")
    # Unknown type - default to false?
    return False


def convert_to_float(value: Any) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def convert_sample_rate(value: Any) -> Optional[int]:
    """
    Converts sample rate to integer, ensuring it's between 0 and 100.
    Allows None as a valid value.
    """
    if value is None:
        return None
    try:
        rate = int(value)
        if not (0 <= rate <= 100):
            logger.warning(
                f"Invalid sample rate {rate}. Must be between 0 and 100. "
                "Defaulting to 100."
            )
            return 100
        return rate
    except (TypeError, ValueError):
        logger.warning(
            f"Invalid sample rate {value}. Must be a number between 0 and 100. "
            "Defaulting to 100."
        )
        return 100


def convert_to_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        # Split on commas
        return [item.strip() for item in value.split(",") if item]
    # Unknown type - default to empty?
    return []


def convert_ignore_paths(value: Any) -> List[str]:
    """
    Removes leading slashes from paths and returns a list of strings.
    """
    raw_paths = convert_to_list(value)
    return [_strip_leading_slash(path) for path in raw_paths]


def convert_endpoint_sampling(value: Union[str, Dict[str, Any]]) -> Dict[str, int]:
    """
    Converts endpoint sampling configuration from string or dict format
    to a normalized dict.
    Example: '/endpoint:40,/test:0' -> {'/endpoint': 40, '/test': 0}
    """
    if isinstance(value, dict):
        return {_strip_leading_slash(k): int(v) for k, v in value.items()}
    if isinstance(value, str):
        if not value.strip():
            return {}
        result = {}
        pairs = [pair.strip() for pair in value.split(",")]
        for pair in pairs:
            try:
                endpoint, rate = pair.split(":")
                rate_int = int(rate)
                if not (0 <= rate_int <= 100):
                    logger.warning(
                        f"Invalid sampling rate {rate} for endpoint {endpoint}. "
                        "Must be between 0 and 100."
                    )
                    continue
                result[_strip_leading_slash(endpoint)] = rate_int
            except ValueError:
                logger.warning(f"Invalid sampling configuration: {pair}")
                continue
        return result
    return {}


CONVERSIONS = {
    "collect_remote_ip": convert_to_bool,
    "core_agent_download": convert_to_bool,
    "core_agent_launch": convert_to_bool,
    "disabled_instruments": convert_to_list,
    "ignore": convert_ignore_paths,
    "ignore_endpoints": convert_ignore_paths,
    "ignore_jobs": convert_ignore_paths,
    "monitor": convert_to_bool,
    "sample_rate": convert_sample_rate,
    "sample_endpoints": convert_endpoint_sampling,
    "endpoint_sample_rate": convert_sample_rate,
    "sample_jobs": convert_endpoint_sampling,
    "job_sample_rate": convert_sample_rate,
    "shutdown_message_enabled": convert_to_bool,
    "shutdown_timeout_seconds": convert_to_float,
}


scout_config = ScoutConfig()
