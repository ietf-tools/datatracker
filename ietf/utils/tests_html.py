from textwrap import dedent

from ietf.utils.tests import TestCase
from ietf.utils.html import clean_html


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
        <div class="polyglot cross-site scripting">
        jaVasCript:/*-/*`/*`/*'/*"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>x3csVg/<sVg/oNloAd=alert()//>x3e
        </div>
        </div>
        """
    ).strip()
    
    # sanitized html with no xss payload
    SAMPLE_HTML_SANITIZED = dedent(
        """
        <div>
        <h1>IETF HTML Test File</h1>
        <p>The file contains a bunch of constructs to test HTML sanitziation</p>
        <div>
        <h2>Links</h2>
        <ul>
        <li><a href="https://example.com" rel="noopener noreferrer">https://example.com</a></li>
        <li><a href="mailto:user@example.com" rel="noopener noreferrer">Example</a></li>
        <li>RFC2119</li>
        <li>draft-ietf-opsec-indicators-of-compromise</li>
        </ul>
        </div>
        <div>
        jaVasCript:/*-/*`/*`/*'/*"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//x3csVg/x3e
        </div>
        </div>
        """
    ).strip()
    
    def test_nh3_cleaner(self):
        result = clean_html(self.SAMPLE_HTML)
        self.assertHTMLEqual(result, self.SAMPLE_HTML_SANITIZED)
