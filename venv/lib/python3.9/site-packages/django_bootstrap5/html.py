from copy import copy

from django.forms.utils import flatatt
from django.utils.html import format_html

from django_bootstrap5.core import get_bootstrap_setting
from django_bootstrap5.text import text_value
from django_bootstrap5.utils import get_url_attrs


def render_script_tag(url):
    """Build a script tag."""
    return render_tag("script", get_url_attrs(url, attr_name="src"))


def render_link_tag(url):
    """Build a link tag."""
    attrs = get_url_attrs(url, attr_name="href")
    attrs["rel"] = "stylesheet"
    return render_tag("link", attrs=attrs, close=False)


def has_prefix(name, prefixes):
    """Return whether the name has one of the given prefixes."""
    return name.startswith(tuple(f"{prefix}_" for prefix in prefixes))


def hyphenate(attr_name):
    """Return the hyphenated version of the attribute name."""
    return attr_name.replace("_", "-")


def render_tag(tag, attrs=None, content=None, close=True):
    """Render an HTML tag."""
    prefixes = get_bootstrap_setting("hyphenate_attribute_prefixes") or []
    if attrs:
        for attr_name, attr_value in copy(attrs).items():
            if has_prefix(attr_name, prefixes):
                attrs[hyphenate(attr_name)] = attr_value
                del attrs[attr_name]
    attrs_string = flatatt(attrs) if attrs else ""
    builder = "<{tag}{attrs}>{content}"
    content_string = text_value(content)
    if content_string or close:
        builder += "</{tag}>"
    return format_html(builder, tag=tag, attrs=attrs_string, content=content_string)
