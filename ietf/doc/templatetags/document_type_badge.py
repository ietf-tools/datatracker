# Copyright The IETF Trust 2015-2020, All Rights Reserved
from django import template
from django.template.loader import render_to_string
# from django.urls import reverse

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

    return render_to_string(
        "doc/badge/doc-badge-other.html",
        {"doc": doc, "snapshot": snapshot},
    )
