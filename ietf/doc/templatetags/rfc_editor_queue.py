# Copyright The IETF Trust 2026, All Rights Reserved

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def rfc_editor_queue_link(doc):
    url = f"{settings.RFC_EDITOR_QUEUE_SITE_BASE_URL}/#{doc.name}"
    status = doc.rfc_editor_queue_status()
    parts = status.split(", ") if status else []
    final_review = "In Final Review"
    if final_review in parts:
        parts.remove(final_review)
        remaining = [
            "Blocked" + part.removeprefix("blocked")
            if part == "blocked" or part.startswith("blocked:")
            else part
            for part in parts
        ]
        status = final_review
        if remaining:
            status += ". " + ", ".join(remaining)

        # Document tables already loaded the URL with the status. Other callers
        # can resolve it from the same auth48 entry maintained by the RPC sync.
        if hasattr(doc, "rfc_editor_final_review_url"):
            final_review_url = doc.rfc_editor_final_review_url
        else:
            final_review_url = (
                doc.documenturl_set.filter(tag_id="auth48")
                .values_list("url", flat=True)
                .first()
            )
        url = final_review_url or url
    return {"url": url, "status": status}
