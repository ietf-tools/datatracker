from django.apps import AppConfig
from django.core.checks import Warning, register

from .templatetags.django_vite import DjangoViteAssetLoader


class DjangoViteAppConfig(AppConfig):
    name = "django_vite"
    verbose_name = "Django Vite"

    def ready(self) -> None:
        try:
            # Create Loader instance at startup to prevent threading problems.
            DjangoViteAssetLoader.instance()
        except RuntimeError:
            # Just continue, the system check below outputs a warning.
            pass


@register
def check_loader_instance(**kwargs):
    """Raise a warning during startup when instance retrieval fails."""

    try:
        # Make Loader instance at startup to prevent threading problems
        DjangoViteAssetLoader.instance()
        return []
    except RuntimeError as exception:
        return [
            Warning(
                exception,
                id="DJANGO_VITE",
                hint=(
                    "Make sure you have generated a manifest file, "
                    "and that the DJANGO_VITE_MANIFEST_PATH points "
                    "to the correct location."
                ),
            )
        ]
