from typing import Any, Dict, Optional, Set, Tuple

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver
from rest_framework.settings import import_from_string, perform_import


class PackageSettings:
    """
    Copy of DRF APISettings class with support for importing settings that
    are dicts with value as a string representing the path to the class
    to be imported.
    """

    setting_name = "DRF_STANDARDIZED_ERRORS"

    def __init__(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        import_strings: Optional[Tuple[str, ...]] = None,
    ):
        self.defaults = defaults or DEFAULTS
        self.import_strings = import_strings or IMPORT_STRINGS
        self._cached_attrs: Set[str] = set()

    @property
    def user_settings(self) -> Dict[str, Any]:
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, self.setting_name, {})
        return self._user_settings

    def __getattr__(self, attr: str) -> Any:
        if attr not in self.defaults:
            raise AttributeError(f"Invalid API setting: '{attr}'")

        try:
            # Check if present in user settings
            val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Coerce import strings into classes
        if attr in self.import_strings:
            if isinstance(val, dict):
                val = {
                    status_code: import_from_string(error_schema, attr)
                    for status_code, error_schema in val.items()
                }
            else:
                val = perform_import(val, attr)

        # Cache the result
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    def reload(self) -> None:
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


DEFAULTS: Dict[str, Any] = {
    "EXCEPTION_HANDLER_CLASS": "drf_standardized_errors.handler.ExceptionHandler",
    "EXCEPTION_FORMATTER_CLASS": "drf_standardized_errors.formatter.ExceptionFormatter",
    "ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": False,
    "NESTED_FIELD_SEPARATOR": ".",
    "ALLOWED_ERROR_STATUS_CODES": [
        "400",
        "401",
        "403",
        "404",
        "405",
        "406",
        "415",
        "429",
        "500",
    ],
    "ERROR_SCHEMAS": None,
    "LIST_INDEX_IN_API_SCHEMA": "INDEX",
    "DICT_KEY_IN_API_SCHEMA": "KEY",
    "ERROR_COMPONENT_NAME_SUFFIX": "ErrorComponent",
}

IMPORT_STRINGS = (
    "EXCEPTION_FORMATTER_CLASS",
    "EXCEPTION_HANDLER_CLASS",
    "ERROR_SCHEMAS",
)

package_settings = PackageSettings(DEFAULTS, IMPORT_STRINGS)


@receiver(setting_changed)
def reload_package_settings(*args: Any, **kwargs: Any) -> None:
    setting = kwargs["setting"]
    if setting == package_settings.setting_name:
        package_settings.reload()
