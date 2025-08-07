from django.template.defaultfilters import capfirst
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .css import merge_css_classes
from .html import render_tag
from .size import DEFAULT_SIZE, SIZE_MD, get_size_class

ALERT_TYPES = ["primary", "secondary", "success", "danger", "warning", "info", "light", "dark"]


def render_alert(
    content,
    *,
    alert_type="info",
    dismissible=True,
    extra_classes="",
):
    """Render a Bootstrap alert."""
    button = ""
    if alert_type not in ALERT_TYPES:
        raise ValueError(f"Value {alert_type} is not a valid alert type. Please choose from {', '.join(ALERT_TYPES)}.")
    css_classes = [f"alert alert-{alert_type}"]
    if dismissible:
        css_classes.append("alert-dismissible fade show")
        close = capfirst(_("close"))
        button = f'<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="{close}"></button>'
    css_classes = merge_css_classes(*css_classes, extra_classes)
    return render_tag(
        "div",
        attrs={"class": css_classes, "role": "alert"},
        content=format_html("{content}" + button, content=content),
    )


def render_button(
    content,
    *,
    button_type=None,
    button_class="btn-primary",
    size="",
    href="",
    extra_classes="",
    **kwargs,
):
    """Render a button with content."""
    attrs = {}
    attrs.update(kwargs)
    size_class = get_size_class(size, prefix="btn", skip=SIZE_MD, default=DEFAULT_SIZE)
    classes = merge_css_classes("btn", button_class, size_class)
    tag = "button"

    if button_type:
        if button_type not in ("submit", "reset", "button", "link"):
            raise ValueError(
                'Parameter "button_type" should be "submit", "reset", "button", "link" or empty '
                f'("{button_type}" given).'
            )
        if button_type != "link":
            attrs["type"] = button_type

    if href:
        if button_type and button_type != "link":
            raise ValueError(f'Button of type "{button_type}" is not allowed a "href" parameter.')
        tag = "a"
        attrs["href"] = href
        attrs.setdefault("role", "button")

    classes = merge_css_classes(classes, extra_classes)
    attrs["class"] = classes

    return render_tag(tag, attrs=attrs, content=content)
