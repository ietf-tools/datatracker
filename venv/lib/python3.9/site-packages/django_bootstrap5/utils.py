from urllib.parse import parse_qs, urlparse, urlunparse

from django.template.loader import get_template
from django.utils.encoding import force_str
from django.utils.http import urlencode
from django.utils.safestring import mark_safe


def render_template_file(template, context=None):
    """Return rendered template file, with given context as input."""
    template = get_template(template)
    return template.render(context)


def url_replace_param(url, name, value):
    """Replace a GET parameter in a URL."""
    url_components = urlparse(force_str(url))

    params = parse_qs(url_components.query)

    if value is None:
        del params[name]
    else:
        params[name] = value

    return mark_safe(
        urlunparse(
            [
                url_components.scheme,
                url_components.netloc,
                url_components.path,
                url_components.params,
                urlencode(params, doseq=True),
                url_components.fragment,
            ]
        )
    )


def get_url_attrs(url, attr_name):
    """
    Return dictionary with attributes for HTML tag, updated with key `attr_name` with value `url`.

    Parameter `url` is either a string or a dict of attrs with the key `url`.
    Parameter `attr_key` is the name for the url value in the results.
    """
    url_attrs = {}
    if isinstance(url, str):
        url = {"url": url}
    url_attrs.update(url)
    url_attrs[attr_name] = url_attrs.pop("url")
    return url_attrs
