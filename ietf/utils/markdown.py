# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Markdown wrapper

Use this instead of importing markdown directly to guarantee consistent extensions / options through
the datatracker.
"""
import markdown as python_markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor

from django.utils.safestring import mark_safe

from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from ietf.utils.text import bleach_cleaner, bleach_linker


class LinkifyExtension(Extension):
    """
    Simple Markdown extension inspired by https://github.com/daGrevis/mdx_linkify,
    but using our bleach_linker directly. Doing the linkification on the converted
    Markdown output introduces artifacts.
    """

    def extendMarkdown(self, md):
        md.postprocessors.register(LinkifyPostprocessor(md), "linkify", 50)
        # disable automatic links via angle brackets for email addresses
        md.inlinePatterns.deregister("automail")
        # "autolink" for URLs does not seem to cause issues, so leave it on


class LinkifyPostprocessor(Postprocessor):
    def run(self, text):
        return urlize_ietf_docs(bleach_linker.linkify(text))


def markdown(text):
    return mark_safe(
        bleach_cleaner.clean(
            python_markdown.markdown(
                text,
                extensions=[
                    "extra",
                    "nl2br",
                    "sane_lists",
                    "toc",
                    LinkifyExtension(),
                ],
            )
        )
    )
