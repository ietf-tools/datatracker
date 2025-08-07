from typing import Final

import jinja2
from jinja2.ext import Extension

from . import components, core, css, forms
from .templatetags import django_bootstrap5 as tags

__all__ = ["BootstrapTags"]

_PREFIX: Final = "bootstrap_"


def get_language_code(context) -> str:
    language_code: None | str

    # recycle `LANGUAGE_CODE` if it exists
    language_code = context.get("LANGUAGE_CODE")
    if language_code:
        return language_code

    # check for a request object to extract the language from
    request = context.get("request")
    language_code = getattr(request, "LANGUAGE_CODE")
    if language_code:
        return language_code

    # defer expensive django import (python caches imports)
    from django.utils.translation import get_language

    return get_language.get_language()


def pagination(context, page, **kwargs) -> str:
    from django.template.loader import render_to_string

    context = dict(context)
    context.update(tags.bootstrap_pagination(page, **kwargs))
    return render_to_string("django_bootstrap5/pagination.html", context=context)


class BootstrapTags(Extension):
    def __init__(self, environment: jinja2.Environment):
        super().__init__(environment)

        self.environment.globals.update(
            {
                f"{_PREFIX}alert": components.render_alert,
                f"{_PREFIX}button": components.render_button,
                f"{_PREFIX}css": tags.bootstrap_css,
                f"{_PREFIX}css_url": core.css_url,
                f"{_PREFIX}field": forms.render_field,
                f"{_PREFIX}form": forms.render_form,
                f"{_PREFIX}form_errors": forms.render_form_errors,
                f"{_PREFIX}formset": forms.render_formset,
                f"{_PREFIX}formset_errors": forms.render_formset_errors,
                f"{_PREFIX}javascript": tags.bootstrap_javascript,
                f"{_PREFIX}javascript_url": core.javascript_url,
                f"{_PREFIX}label": forms.render_label,
                f"{_PREFIX}messages": jinja2.pass_context(lambda ctx: tags.bootstrap_messages(dict(ctx))),
                f"{_PREFIX}pagination": jinja2.pass_context(pagination),
                # undocumented private functions
                f"{_PREFIX}setting": core.get_bootstrap_setting,
                f"{_PREFIX}server_side_validation_class": (tags.bootstrap_server_side_validation_class),
                f"{_PREFIX}classes": css.merge_css_classes,
                f"{_PREFIX}language_code": jinja2.pass_context(get_language_code),
            }
        )
