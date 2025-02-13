# Copyright The IETF Trust 2025, All Rights Reserved
import rfc2html

from django.conf import settings
from django.utils.safestring import SafeString, mark_safe
from django.utils.html import format_html


def make_htmlized_fragment(text: str) -> SafeString:
    """Generate an htmlized HTML fragment from document text"""
    # The path here has to match the urlpattern for htmlized
    # documents in order to produce correct intra-document links
    html = mark_safe(rfc2html.markup(text, path=settings.HTMLIZER_URL_PREFIX))
    html = format_html(
        '<div class="rfcmarkup">{}</div>', 
        html,
    )
    return html
