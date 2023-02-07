# Copyright The IETF Trust 2023, All Rights Reserved
"""Markdown API utilities tests"""

from textwrap import dedent

from ietf.utils.tests import TestCase
from ietf.utils.markdown import markdown


class MarkdownTests(TestCase):
    SAMPLE_MARKDOWN = dedent(
        """
        # IETF Markdown Test File

        This file contains a bunch of constructs to test our markdown converter in
        `ietf/utils/markdown.py`.

        ## Links

        * https://example.com
        * <https://example.com>
        * [Example](https://example.com)
        * user@example.com
        * <user@example.com>
        * [User](mailto:user@example.com)
        * RFC2119
        * BCP 3
        * STD  1
        * FYI2
        * draft-ietf-opsec-indicators-of-compromise
        * draft-ietf-opsec-indicators-of-compromise-01
        """
    )

    SAMPLE_MARKDOWN_OUTPUT = dedent(
        """
        <h1 id="ietf-markdown-test-file">IETF Markdown Test File</h1>
        <p>This file contains a bunch of constructs to test our markdown converter in<br>
        <code>ietf/utils/<a href="http://markdown.py">markdown.py</a></code>.</p>
        <h2 id="links">Links</h2>
        <ul>
        <li><a href="https://example.com">https://example.com</a></li>
        <li><a href="https://example.com">https://example.com</a></li>
        <li><a href="https://example.com">Example</a></li>
        <li><a href="mailto:user@example.com">user@example.com</a></li>
        <li>&lt;<a href="mailto:user@example.com">user@example.com</a>&gt;</li>
        <li><a href="mailto:user@example.com">User</a></li>
        <li>RFC2119</li>
        <li>BCP 3</li>
        <li>STD  1</li>
        <li>FYI2</li>
        <li>draft-ietf-opsec-indicators-of-compromise</li>
        <li>draft-ietf-opsec-indicators-of-compromise-01</li>
        </ul>
        """
    ).strip()

    def test_markdown(self):
        result = markdown(self.SAMPLE_MARKDOWN)
        self.assertEqual(result, self.SAMPLE_MARKDOWN_OUTPUT)
