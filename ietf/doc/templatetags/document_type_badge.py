# Copyright The IETF Trust 2015-2020, All Rights Reserved
from django import template
from django.conf import settings
from django.template.loader import render_to_string

from warnings import warn

# from ietf.group.models import Group
# from ietf.name.models import GroupTypeName

register = template.Library()


@register.simple_tag
def document_type_badge(doc, snapshot):
    if doc.type == "rfc":
        return render_to_string(
            "doc/badge/doc-badge-rfc.html",
            {"doc": doc, "snapshot": snapshot},
        )
    elif doc.type == "draft":
        return render_to_string(
            "doc/badge/doc-badge-draft.html",
            {"doc": doc, "snapshot": snapshot},
        )
    else:
        error_message = f"Unsupported document type {doc.type}."
        if settings.SERVER_MODE != 'production':
            raise ValueError(error_message)
        else:
            warn(error_message)
        return ""
