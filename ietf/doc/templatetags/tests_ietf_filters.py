# Copyright The IETF Trust 2022, All Rights Reserved

from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from ietf.utils.test_utils import TestCase

import debug # pyflakes: ignore
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
                "draft-ietf-rfc9999-bis-01.txt",
                '<a href="/doc/draft-ietf-rfc9999-bis/01/">draft-ietf-rfc9999-bis-01.txt</a>',
            ),
            (
                "foo RFC 9999 draft-ietf-rfc9999-bis-01 bar",
                'foo <a href="/doc/rfc9999/">RFC 9999</a> <a href="/doc/draft-ietf-rfc9999-bis/01/">draft-ietf-rfc9999-bis-01</a> bar',
            ),
            (
                "New version available: <b>draft-bryan-sipping-p2p-03.txt</b>",
                'New version available: <b><a href="/doc/draft-bryan-sipping-p2p/03/">draft-bryan-sipping-p2p-03.txt</a></b>',
            ),
            (
                "New version available: <b>charter-ietf-6man-04.txt</b>",
                'New version available: <b><a href="/doc/charter-ietf-6man/04/">charter-ietf-6man-04.txt</a></b>'
            ),
            (
                "New version available: <b>charter-ietf-6man-03-07.txt</b>",
                'New version available: <b><a href="/doc/charter-ietf-6man/03-07/">charter-ietf-6man-03-07.txt</a></b>'
            ),
            (
                "repository https://github.com/tlswg/draft-ietf-tls-ticketrequest",
                'repository https://github.com/tlswg/draft-ietf-tls-ticketrequest'
            ),
            (
                "draft-madanapalli-nd-over-802.16-problems",
                '<a href="/doc/draft-madanapalli-nd-over-802.16-problems/">draft-madanapalli-nd-over-802.16-problems</a>'
            ),
            (
                 "draft-madanapalli-nd-over-802.16-problems-02.txt",
                '<a href="/doc/draft-madanapalli-nd-over-802.16-problems/02/">draft-madanapalli-nd-over-802.16-problems-02.txt</a>'
            ),
            (
                '<a href="mailto:draft-ietf-some-names@ietf.org">draft-ietf-some-names@ietf.org</a>',
                '<a href="mailto:draft-ietf-some-names@ietf.org">draft-ietf-some-names@ietf.org</a>',
            ),
            (
                "http://ieee802.org/1/files/public/docs2015/cn-thaler-Qcn-draft-PAR.pdf",
                "http://ieee802.org/1/files/public/docs2015/cn-thaler-Qcn-draft-PAR.pdf"
            )
        ]

        # Some edge cases scraped from existing old draft names
        for name in [
            # "draft-odell-8+8", # This fails since + matches the right side of \b
            # "draft-durand-gse+", # same failure
            "draft-kim-xcast+-few-2-few",
            #"draft-ietf-pem-ansix9.17",  # Fails because of not being greedy with . before txt
        ]:
            cases.append((name,f'<a href="/doc/{name}/">{name}</a>'))

        for input, output in cases:
            #debug.show("(urlize_ietf_docs(input),output)")
            self.assertEqual(urlize_ietf_docs(input), output)
