from math import floor
from urllib.parse import parse_qs, urlparse, urlunparse

from django import template
from django.contrib.messages import constants as message_constants
from django.template import Context
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

from ..components import render_alert, render_button
from ..core import css_url, get_bootstrap_setting, javascript_url, theme_url
from ..css import _css_class_list, merge_css_classes
from ..forms import (
    render_field,
    render_form,
    render_form_errors,
    render_formset,
    render_formset_errors,
    render_label,
)
from ..html import render_link_tag, render_script_tag
from ..size import get_size_class
from ..utils import render_template_file, url_replace_param

MESSAGE_ALERT_TYPES = {
    message_constants.DEBUG: "warning",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

register = template.Library()


@register.simple_tag
def bootstrap_setting(value):
    """
    Return django-bootstrap5 setting for use in in a template.

    Please consider this tag private, do not use it in your own templates.
    """
    return get_bootstrap_setting(value)


@register.simple_tag
def bootstrap_server_side_validation_class(widget):
    """
    Return server side validation class from a widget.

    Please consider this tag private, do not use it in your own templates.
    """
    try:
        css_classes = _css_class_list([widget["attrs"]["class"]])
    except KeyError:
        return ""
    return " ".join([css_class for css_class in css_classes if css_class in ["is-valid", "is-invalid"]])


@register.simple_tag
def bootstrap_classes(*args):
    """
    Return list of classes.

    Please consider this filter private, do not use it in your own templates.
    """
    return merge_css_classes(*args)


@register.filter
def bootstrap_message_alert_type(message):
    """Return the alert type for a message, defaults to `info`."""
    try:
        level = message.level
    except AttributeError:
        pass
    else:
        try:
            return MESSAGE_ALERT_TYPES[level]
        except KeyError:
            pass
    return "info"


@register.simple_tag
def bootstrap_javascript_url():
    """
    Return the full url to the Bootstrap JavaScript library.

    Default value: ``None``

    This value is configurable, see Settings section

    **Tag name**::

        bootstrap_javascript_url

    **Usage**::

        {% bootstrap_javascript_url %}

    **Example**::

        {% bootstrap_javascript_url %}
    """
    return javascript_url()


@register.simple_tag
def bootstrap_css_url():
    """
    Return the full url to the Bootstrap CSS library.

    Default value: ``None``

    This value is configurable, see Settings section

    **Tag name**::

        bootstrap_css_url

    **Usage**::

        {% bootstrap_css_url %}

    **Example**::

        {% bootstrap_css_url %}
    """
    return css_url()


@register.simple_tag
def bootstrap_theme_url():
    """
    Return the full url to a Bootstrap theme CSS library.

    Default value: ``None``

    This value is configurable, see Settings section

    **Tag name**::

        bootstrap_theme_url

    **Usage**::

        {% bootstrap_theme_url %}

    **Example**::

        {% bootstrap_theme_url %}
    """
    return theme_url()


@register.simple_tag
def bootstrap_css():
    """
    Return HTML for Bootstrap CSS, or empty string if no CSS url is available.

    Default value: ``None``

    This value is configurable, see Settings section

    **Tag name**::

        bootstrap_css

    **Usage**::

        {% bootstrap_css %}

    **Example**::

        {% bootstrap_css %}
    """
    rendered_urls = []
    if bootstrap_css_url():
        rendered_urls.append(render_link_tag(bootstrap_css_url()))
    if bootstrap_theme_url():
        rendered_urls.append(render_link_tag(bootstrap_theme_url()))
    return mark_safe("".join([url for url in rendered_urls]))


@register.simple_tag
def bootstrap_javascript():
    """
    Return HTML for Bootstrap JavaScript, or empty string if no JavaScript URL is available.

    Adjust url in settings.
    If no url is returned, we don't want this statement to return any HTML. This is intended behavior.

    Default value: False

    This value is configurable, see Settings section. Note that any value that evaluates to True and is
    not "slim" will be interpreted as True.

    **Tag name**::

        bootstrap_javascript

    **Usage**::

        {% bootstrap_javascript %}

    **Example**::

        {% bootstrap_javascript %}
    """
    # List of JS tags to include
    javascript_tags = []

    # Bootstrap JavaScript
    bootstrap_js_url = bootstrap_javascript_url()
    if bootstrap_js_url:
        javascript_tags.append(render_script_tag(bootstrap_js_url))

    # Join and return
    return mark_safe("\n".join(javascript_tags))


@register.simple_tag
def bootstrap_formset(formset, **kwargs):
    """
    Render a formset.

    **Tag name**::

        bootstrap_formset

    **Parameters**::

        formset
            The formset that is being rendered


        See bootstrap_field_ for other arguments

    **Usage**::

        {% bootstrap_formset formset %}

    **Example**::

        {% bootstrap_formset formset layout='horizontal' %}
    """
    return render_formset(formset, **kwargs)


@register.simple_tag
def bootstrap_formset_errors(formset, **kwargs):
    """
    Render formset errors.

    **Tag name**::

        bootstrap_formset_errors

    **Parameters**::

        formset
            The formset that is being rendered

        layout
            Context value that is available in the template ``django_bootstrap5/form_errors.html`` as ``layout``.

    **Usage**::

        {% bootstrap_formset_errors formset %}

    **Example**::

        {% bootstrap_formset_errors formset layout='inline' %}
    """
    return render_formset_errors(formset, **kwargs)


@register.simple_tag
def bootstrap_form(form, **kwargs):
    """
    Render a form.

    **Tag name**::

        bootstrap_form

    **Parameters**::

        form
            The form that is to be rendered

        exclude
            A list of field names (comma separated) that should not be rendered
            E.g. exclude=subject,bcc

        alert_error_type
            Control which type of errors should be rendered in global form alert.

                One of the following values:

                    * ``'all'``
                    * ``'fields'``
                    * ``'non_fields'``

                :default: ``'non_fields'``

        See bootstrap_field_ for other arguments

    **Usage**::

        {% bootstrap_form form %}

    **Example**::

        {% bootstrap_form form layout='inline' %}
    """
    return render_form(form, **kwargs)


@register.simple_tag
def bootstrap_form_errors(form, **kwargs):
    """
    Render form errors.

    **Tag name**::

        bootstrap_form_errors

    **Parameters**::

        form
            The form that is to be rendered

        type
            Control which type of errors should be rendered.

            One of the following values:

                * ``'all'``
                * ``'fields'``
                * ``'non_fields'``

            :default: ``'all'``

        layout
            Context value that is available in the template ``django_bootstrap5/form_errors.html`` as ``layout``.

    **Usage**::

        {% bootstrap_form_errors form %}

    **Example**::

        {% bootstrap_form_errors form layout='inline' %}
    """
    return render_form_errors(form, **kwargs)


@register.simple_tag
def bootstrap_field(field, **kwargs):
    """
    Render a field.

    **Tag name**::

        bootstrap_field

    **Parameters**::


        field
            The form field to be rendered

        layout
            If set to ``'horizontal'`` then the field and label will be rendered side-by-side.
            If set to ``'floating'`` then support widgets will use floating labels.
            Layout set in ``'bootstrap_form'`` takes precedence over layout set in ``'bootstrap_formset'``.
            Layout set in ``'bootstrap_field'`` takes precedence over layout set in ``'bootstrap_form'``.

        wrapper_class
            CSS class of the ``div`` that wraps the field and label.

            :default: ``'mb-3'``

        field_class
            CSS class of the ``div`` that wraps the field.

        label_class
            CSS class of the ``label`` element. Will always have ``control-label`` as the last CSS class.

        show_help
            Show the field's help text, if the field has help text.

            :default: ``True``

        show_label
            Whether the show the label of the field.

                * ``True``
                * ``False``/``'visually-hidden'``
                * ``'skip'``

            :default: ``True``

        exclude
            A list of field names that should not be rendered

        size
            Controls the size of the rendered ``div.row`` through the use of CSS classes.

            One of the following values:

                * ``'small'``
                * ``'medium'``
                * ``'large'``

        placeholder
            Sets the placeholder text of a textbox

        horizontal_label_class
            Class used on the label when the ``layout`` is set to ``horizontal``.

            :default: ``'col-md-3'``. Can be changed in :doc:`settings`

        horizontal_field_class
            Class used on the field when the ``layout`` is set to ``horizontal``.

            :default: ``'col-md-9'``. Can be changed in :doc:`settings`

        addon_before
            Text that should be prepended to the form field. Can also be an icon, e.g.
            ``'<span class="glyphicon glyphicon-calendar"></span>'``

            See the `Bootstrap docs <http://getbootstrap.com/components/#input-groups-basic>` for more examples.

        addon_after
            Text that should be appended to the form field. Can also be an icon, e.g.
            ``'<span class="glyphicon glyphicon-calendar"></span>'``

            See the `Bootstrap docs <http://getbootstrap.com/components/#input-groups-basic>` for more examples.

        addon_before_class
            Class used on the span when ``addon_before`` is used.

            One of the following values:

                * ``'input-group-text'``
                * ``None``

            Set to None to disable the span inside the addon. (for use with buttons)

            :default: ``input-group-text``

        addon_after_class
            Class used on the span when ``addon_after`` is used.

            One of the following values:

                * ``'input-group-text'``
                * ``None``

            Set to None to disable the span inside the addon. (for use with buttons)

            :default: ``input-group-text``

        error_css_class
            CSS class used when the field has an error

            :default: ``'has-error'``. Can be changed :doc:`settings`

        required_css_class
            CSS class used on the ``div.row`` to indicate a field is required

            :default: ``''``. Can be changed :doc:`settings`

        success_css_class
            CSS class used when the field has valid data

            :default: ``'has-success'``. Can be changed :doc:`settings`

    **Usage**::

        {% bootstrap_field field %}

    **Example**::

        {% bootstrap_field field show_label=False %}
    """
    return render_field(field, **kwargs)


@register.simple_tag
def bootstrap_label(content, **kwargs):
    """
    Render a label.

    **Tag name**::

        bootstrap_label

    **Parameters**::

        content
            The label's text

        label_for
            The value that will be in the ``for`` attribute of the rendered ``<label>``

        label_class
            The CSS class for the rendered ``<label>``

        label_title
            The value that will be in the ``title`` attribute of the rendered ``<label>``

    **Usage**::

        {% bootstrap_label content %}

    **Example**::

        {% bootstrap_label "Email address" label_for="exampleInputEmail1" %}
    """
    return render_label(content, **kwargs)


@register.simple_tag
def bootstrap_button(content, **kwargs):
    """
    Render a button.

    **Tag name**::

        bootstrap_button

    **Parameters**::

        content
            The text to be displayed in the button

        button_type
            Optional field defining what type of button this is.

            Accepts one of the following values:

                * ``'submit'``
                * ``'reset'``
                * ``'button'``
                * ``'link'``

        button_class
            The class of button to use. If none is given, btn-primary will be used.

        extra_classes
            Any extra CSS classes that should be added to the button.

        size
            Optional field to control the size of the button.

            Accepts one of the following values:

                * ``'sm'``
                * ``'md'`` (default)
                * ``'lg'``

        href
            Render the button as an ``<a>`` element. The ``href`` attribute is set with this value.
            If a ``button_type`` other than ``link`` is defined, specifying a ``href`` will throw a
            ``ValueError`` exception.

        name
            Value of the ``name`` attribute of the rendered element.

        value
            Value of the ``value`` attribute of the rendered element.

        **kwargs
            All other keywords arguments will be passed on as HTML attributes.

    **Usage**::

        {% bootstrap_button content %}

    **Example**::

        {% bootstrap_button "Save" button_type="submit" button_class="btn-primary" %}
    """
    return render_button(content, **kwargs)


@register.simple_tag
def bootstrap_alert(content, **kwargs):
    """
    Render an alert.

    **Tag name**::

        bootstrap_alert

    **Parameters**::

        content
            HTML content of alert

        alert_type
            * ``'info'``
            * ``'warning'``
            * ``'danger'``
            * ``'success'``

            :default: ``'info'``

        dismissible
            boolean, is alert dismissible

            :default: ``True``

        extra_classes
            string, extra CSS classes for alert

            :default: ""

    **Usage**::

        {% bootstrap_alert content %}

    **Example**::

        {% bootstrap_alert "Something went wrong" alert_type="error" %}
    """
    return render_alert(content, **kwargs)


@register.simple_tag(takes_context=True)
def bootstrap_messages(context):
    """
    Show django.contrib.messages Messages in Bootstrap alert containers.

    Uses the template ``django_bootstrap5/messages.html``.

    **Tag name**::

        bootstrap_messages

    **Parameters**::

        None.

    **Usage**::

        {% bootstrap_messages %}

    **Example**::

        {% bootstrap_messages %}
    """
    if isinstance(context, Context):
        context = context.flatten()
    context.update({"message_constants": message_constants})
    return render_template_file("django_bootstrap5/messages.html", context=context)


@register.inclusion_tag("django_bootstrap5/pagination.html")
def bootstrap_pagination(page, **kwargs):
    """
    Render pagination for a page.

    **Tag name**::

        bootstrap_pagination

    **Parameters**::

        page
            The page of results to show.

        pages_to_show
            Number of pages in total

            :default: ``11``

        url
            URL to navigate to for pagination forward and pagination back.

            :default: ``None``

        size
            Controls the size of the pagination through CSS. Defaults to being normal sized.

            One of the following:

                * ``'small'``
                * ``'large'``

            :default: ``None``

        justify_content
            Controls the alignment of the pagination through CSS. Defaults to no alignment.

            One of the following:

                * ``'start'``
                * ``'center'``
                * ``'end'``

            :default: ``None``

        extra
            Any extra page parameters.

            :default: ``None``

        parameter_name
            Name of the paging URL parameter.

            :default: ``'page'``

    **Usage**::

        {% bootstrap_pagination page %}

    **Example**::

        {% bootstrap_pagination lines url="/pagination?page=1" size="large" %}
    """
    pagination_kwargs = kwargs.copy()
    pagination_kwargs["page"] = page
    return get_pagination_context(**pagination_kwargs)


@register.simple_tag
def bootstrap_url_replace_param(url, name, value):
    return url_replace_param(url, name, value)


def get_pagination_context(
    page,
    *,
    pages_to_show=11,
    url=None,
    size=None,
    justify_content=None,
    extra=None,
    parameter_name="page",
):
    """Generate Bootstrap pagination context from a page object."""
    pages_to_show = int(pages_to_show)
    if pages_to_show < 1:
        raise ValueError(f"Pagination pages_to_show should be a positive integer, you specified {pages_to_show}.")

    num_pages = page.paginator.num_pages
    current_page = page.number

    delta_pages = int(floor(pages_to_show / 2))

    first_page = max(1, current_page - delta_pages)
    pages_back = max(1, first_page - delta_pages) if first_page > 1 else None

    last_page = first_page + pages_to_show - 1
    if pages_back is None:
        last_page += 1
    if last_page > num_pages:
        last_page = num_pages

    if last_page < num_pages:
        pages_forward = min(last_page + delta_pages, num_pages)
    else:
        pages_forward = None
        if first_page > 1:
            first_page -= 1
        if pages_back is not None and pages_back > 1:
            pages_back -= 1
        else:
            pages_back = None

    pages_shown = []
    for i in range(first_page, last_page + 1):
        pages_shown.append(i)

    parts = urlparse(url or "")
    params = parse_qs(parts.query)
    if extra:
        params.update(parse_qs(extra))
    url = urlunparse(
        [
            parts.scheme,
            parts.netloc,
            parts.path,
            parts.params,
            urlencode(params, doseq=True),
            parts.fragment,
        ]
    )

    pagination_css_classes = ["pagination"]
    if size:
        pagination_size_class = get_size_class(size, prefix="pagination", skip="md")
        if pagination_size_class:
            pagination_css_classes.append(pagination_size_class)

    if justify_content:
        if justify_content in ["start", "center", "end"]:
            pagination_css_classes.append(f"justify-content-{justify_content}")
        else:
            raise ValueError(
                f"Invalid value '{justify_content}' for pagination justification."
                " Valid values are 'start', 'center', 'end'."
            )

    return {
        "bootstrap_pagination_url": url,
        "num_pages": num_pages,
        "current_page": current_page,
        "first_page": first_page,
        "last_page": last_page,
        "pages_shown": pages_shown,
        "pages_back": pages_back,
        "pages_forward": pages_forward,
        "pagination_css_classes": " ".join(pagination_css_classes),
        "parameter_name": parameter_name,
    }
