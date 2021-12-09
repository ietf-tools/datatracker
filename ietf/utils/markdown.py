# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Markdown wrapper

Use this instead of importing markdown directly to guarantee consistent extensions / options through
the datatracker.
"""
import bleach
import markdown as python_markdown

from django.utils.safestring import mark_safe
from markdown.extensions.extra import ExtraExtension

ALLOWED_TAGS = bleach.ALLOWED_TAGS + ['p', 'h1', 'h2', 'h3', 'h4', 'br']

def markdown(text):
    return mark_safe(bleach.clean(
        python_markdown.markdown(text, extensions=[ExtraExtension()]),
        tags=ALLOWED_TAGS,
    ))
