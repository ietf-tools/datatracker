# Copyright The IETF Trust 2023, All Rights Reserved
"""Markdown API utilities tests"""

from pathlib import Path

from django.conf import settings

from ietf.utils.tests import TestCase
from ietf.utils.markdown import markdown


class MarkdownTests(TestCase):
    SAMPLE_DIR = Path(settings.BASE_DIR) / "utils"
    SAMPLE_MARKDOWN = (SAMPLE_DIR / "markdown-test.md").read_text()
    SAMPLE_MARKDOWN_OUTPUT = (SAMPLE_DIR / "markdown-test.html").read_text()

    def test_markdown(self):
        result = markdown(self.SAMPLE_MARKDOWN)
        self.assertEqual(result, self.SAMPLE_MARKDOWN_OUTPUT)
