from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from ietf.utils.test_utils import TestCase

# TODO: most other filters need test cases, too


class IetfFiltersTests(TestCase):
    def test_urlize_ietf_docs(self):
        cases = [
            ("no change", "no change"),
            ("bcp1", '<a href="/doc/bcp1/">bcp1</a>'),
            ("Std 003", '<a href="/doc/std3/">Std 003</a>'),
            (
                "FYI02 changes Std 003",
                '<a href="/doc/fyi2/">FYI02</a> changes <a href="/doc/std3/">Std 003</a>',
            ),
            ("rfc2119", '<a href="/doc/rfc2119/">rfc2119</a>'),
            ("Rfc 02119", '<a href="/doc/rfc2119/">Rfc 02119</a>'),
            ("draft-abc-123", '<a href="/doc/draft-abc-123/">draft-abc-123</a>'),
            (
                "draft-ietf-rfc9999-bis-01",
                '<a href="/doc/draft-ietf-rfc9999-bis-01/">draft-ietf-rfc9999-bis-01</a>',
            ),
        ]

        for input, output in cases:
            self.assertEqual(urlize_ietf_docs(input), output)
