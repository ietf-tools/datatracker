# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Markdown wrapper

Use this instead of importing markdown directly to guarantee consistent extensions / options through
the datatracker.
"""
import markdown as python_markdown

from django.utils.safestring import mark_safe

from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from ietf.utils.text import (
    bleach_cleaner,
    check_url_validity,
    bleach,
    tlds_sorted,
    protocols,
)
from mdx_linkify.mdx_linkify import LinkifyExtension  # type: ignore


def markdown(text):
    return mark_safe(
        urlize_ietf_docs(
            bleach_cleaner.clean(
                python_markdown.markdown(
                    text,
                    extensions=[
                        "extra",
                        "nl2br",
                        "sane_lists",
                        "toc",
                        LinkifyExtension(
                            # keep these in sync with the bleach_linker initialization
                            linker_options={
                                "callbacks": [check_url_validity],
                                "url_re": bleach.linkifier.build_url_re(
                                    tlds=tlds_sorted, protocols=protocols
                                ),
                                "email_re": bleach.linkifier.build_email_re(
                                    tlds=tlds_sorted
                                ),
                                "parse_email": True,
                            }
                        ),
                    ],
                )
            )
        )
    )
