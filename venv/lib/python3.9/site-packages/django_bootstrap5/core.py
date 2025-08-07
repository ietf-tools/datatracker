from importlib import import_module

from django.conf import settings

BOOTSTRAP5_DEFAULTS = {
    "css_url": {
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        "integrity": "sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH",
        "crossorigin": "anonymous",
    },
    "javascript_url": {
        "url": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        "integrity": "sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz",
        "crossorigin": "anonymous",
    },
    "theme_url": None,
    "color_mode": None,
    "javascript_in_head": False,
    "wrapper_class": "mb-3",
    "inline_wrapper_class": "",
    "horizontal_label_class": "col-sm-2",
    "horizontal_field_class": "col-sm-10",
    "horizontal_field_offset_class": "offset-sm-2",
    "set_placeholder": True,
    "checkbox_layout": None,
    "checkbox_style": None,
    "required_css_class": "",
    "error_css_class": "",
    "success_css_class": "",
    "server_side_validation": True,
    "formset_renderers": {"default": "django_bootstrap5.renderers.FormsetRenderer"},
    "form_renderers": {"default": "django_bootstrap5.renderers.FormRenderer"},
    "field_renderers": {
        "default": "django_bootstrap5.renderers.FieldRenderer",
    },
    "hyphenate_attribute_prefixes": ["data"],
}


def get_bootstrap_setting(name, default=None):
    """
    Read a setting.

    Lookup order is:

    1. Django settings
    2. `django-bootstrap5` defaults
    3. Given default value
    """
    bootstrap5_settings = getattr(settings, "BOOTSTRAP5", {})
    return bootstrap5_settings.get(name, BOOTSTRAP5_DEFAULTS.get(name, default))


def javascript_url():
    """Return the full url to the Bootstrap JavaScript file."""
    return get_bootstrap_setting("javascript_url")


def css_url():
    """Return the full url to the Bootstrap CSS file."""
    return get_bootstrap_setting("css_url")


def theme_url():
    """Return the full url to the theme CSS file."""
    return get_bootstrap_setting("theme_url")


def get_renderer(renderers, **kwargs):
    layout = kwargs.get("layout", "")
    path = renderers.get(layout, renderers["default"])
    mod, cls = path.rsplit(".", 1)
    return getattr(import_module(mod), cls)


def get_formset_renderer(**kwargs):
    renderers = get_bootstrap_setting("formset_renderers")
    return get_renderer(renderers, **kwargs)


def get_form_renderer(**kwargs):
    renderers = get_bootstrap_setting("form_renderers")
    return get_renderer(renderers, **kwargs)


def get_field_renderer(**kwargs):
    renderers = get_bootstrap_setting("field_renderers")
    return get_renderer(renderers, **kwargs)
