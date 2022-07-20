# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Markdown wrapper

Use this instead of importing markdown directly to guarantee consistent extensions / options through
the datatracker.
"""
import markdown as python_markdown

from django.utils.safestring import mark_safe

from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from ietf.utils.text import bleach_cleaner, bleach_linker


def markdown(text):
    return mark_safe(
        bleach_linker.linkify(
            urlize_ietf_docs(
                bleach_cleaner.clean(
                    python_markdown.markdown(
                        text, extensions=["extra", "nl2br", "sane_lists", "toc"]
                    )
                )
            )
        )
    )
