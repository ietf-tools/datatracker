from textwrap import dedent

from ietf.utils.tests import TestCase
from ietf.utils.html import remove_tags, acceptable_tags


class HTMLTests(TestCase):
    SAMPLE_HTML = dedent(
        """
        <div class="ietf-html-test-file">
        <h1>IETF HTML Test File</h1>
        <p>The file contains a bunch of constructs to test HTML sanitziation</p>
        <div class="links">
        <h2>Links</h2>
        <ul>
        <li><a href="https://example.com">https://example.com</a></li>
        <li><a href="mailto:user@example.com">Example</a></li>
        <li>RFC2119</li>
        <li>draft-ietf-opsec-indicators-of-compromise</li>
        </ul>
        </div>
        </div>
        """
    ).strip()
    
    SAMPLE_HTML_NOTAG = dedent(
        """
        IETF HTML Test File
        The file contains a bunch of constructs to test HTML sanitziation
        Links
        https://example.com
        Example
        RFC2119
        draft-ietf-opsec-indicators-of-compromise
        """
    ).strip()
    
    def test_nh3_cleaner(self):
        result = remove_tags(self.SAMPLE_HTML, tags=acceptable_tags)
        self.assertHTMLEqual(result, self.SAMPLE_HTML_NOTAG)
