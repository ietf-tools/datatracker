# Copyright The IETF Trust 2022, All Rights Reserved

from django.conf import settings

from ietf.doc.factories import (
    WgDraftFactory,
    IndividualDraftFactory,
    CharterFactory,
    NewRevisionDocEventFactory,
)
from ietf.doc.models import State, DocEvent, DocAlias
from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs, is_valid_url
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase

import debug  # pyflakes: ignore

# TODO: most other filters need test cases, too


class IetfFiltersTests(TestCase):
    def test_is_valid_url(self):
        cases = [(settings.IDTRACKER_BASE_URL, True), ("not valid", False)]
        for url, result in cases:
            self.assertEqual(is_valid_url(url), result)

    def test_urlize_ietf_docs(self):
        wg_id = WgDraftFactory()
        wg_id.set_state(State.objects.get(type="draft", slug="rfc"))
        wg_id.std_level_id = "bcp"
        wg_id.save_with_history(
            [
                DocEvent.objects.create(
                    doc=wg_id,
                    rev=wg_id.rev,
                    type="published_rfc",
                    by=Person.objects.get(name="(System)"),
                )
            ]
        )
        DocAlias.objects.create(name="rfc123456").docs.add(wg_id)
        DocAlias.objects.create(name="bcp123456").docs.add(wg_id)
        DocAlias.objects.create(name="std123456").docs.add(wg_id)
        DocAlias.objects.create(name="fyi123456").docs.add(wg_id)

        id = IndividualDraftFactory(name="draft-me-rfc123456bis")
        id_num = IndividualDraftFactory(name="draft-rosen-rfcefdp-update-2026")
        id_num_two = IndividualDraftFactory(name="draft-spaghetti-idr-deprecate-8-9-10")
        id_plus = IndividualDraftFactory(name="draft-odell-8+8")
        id_plus_end = IndividualDraftFactory(name="draft-durand-gse+")
        id_dot = IndividualDraftFactory(name="draft-ietf-pem-ansix9.17")
        charter = CharterFactory()
        e = NewRevisionDocEventFactory(doc=charter, rev="01")
        charter.rev = e.rev
        charter.save_with_history([e])
        e = NewRevisionDocEventFactory(doc=charter, rev="01-00")
        charter.rev = e.rev
        charter.save_with_history([e])

        cases = [
            ("no change", "no change"),
            ("bCp123456", '<a href="/doc/bcp123456/">bCp123456</a>'),
            ("Std 00123456", '<a href="/doc/std123456/">Std 00123456</a>'),
            (
                "FyI  0123456 changes std 00123456",
                '<a href="/doc/fyi123456/">FyI  0123456</a> changes <a href="/doc/std123456/">std 00123456</a>',
            ),
            ("rfc123456", '<a href="/doc/rfc123456/">rfc123456</a>'),
            ("Rfc 0123456", '<a href="/doc/rfc123456/">Rfc 0123456</a>'),
            (wg_id.name, f'<a href="/doc/{wg_id.name}/">{wg_id.name}</a>'),
            (
                f"{id.name}-{id.rev}.txt",
                f'<a href="/doc/{id.name}/{id.rev}/">{id.name}-{id.rev}.txt</a>',
            ),
            (
                f"foo RFC 123456 {id.name}-{id.rev} bar",
                f'foo <a href="/doc/rfc123456/">RFC 123456</a> <a href="/doc/{id.name}/{id.rev}/">{id.name}-{id.rev}</a> bar',
            ),
            (
                f"New version available: <b>{id.name}-{id.rev}.txt</b>",
                f'New version available: <b><a href="/doc/{id.name}/{id.rev}/">{id.name}-{id.rev}.txt</a></b>',
            ),
            (
                f"New version available: <b>{charter.name}-{charter.rev}.txt</b>",
                f'New version available: <b><a href="/doc/{charter.name}/{charter.rev}/">{charter.name}-{charter.rev}.txt</a></b>',
            ),
            (
                f"New version available: <b>{charter.name}-01-00.txt</b>",
                f'New version available: <b><a href="/doc/{charter.name}/01-00/">{charter.name}-01-00.txt</a></b>',
            ),
            (
                "repository https://github.com/tlswg/draft-ietf-tls-ticketrequest",
                "repository https://github.com/tlswg/draft-ietf-tls-ticketrequest",
            ),
            (
                '<a href="mailto:draft-ietf-some-names@ietf.org">draft-ietf-some-names@ietf.org</a>',
                '<a href="mailto:draft-ietf-some-names@ietf.org">draft-ietf-some-names@ietf.org</a>',
            ),
            (
                "http://ieee802.org/1/files/public/docs2015/cn-thaler-Qcn-draft-PAR.pdf",
                "http://ieee802.org/1/files/public/docs2015/cn-thaler-Qcn-draft-PAR.pdf",
            ),
            (
                f"{id_num.name}.pdf",
                f'<a href="/doc/{id_num.name}/">{id_num.name}.pdf</a>',
            ),
            (
                f"{id_num.name}-{id_num.rev}.txt",
                f'<a href="/doc/{id_num.name}/{id_num.rev}/">{id_num.name}-{id_num.rev}.txt</a>',
            ),
            (
                f"{id_num_two.name}.pdf",
                f'<a href="/doc/{id_num_two.name}/">{id_num_two.name}.pdf</a>',
            ),
            (
                f"{id_num_two.name}-{id_num_two.rev}.txt",
                f'<a href="/doc/{id_num_two.name}/{id_num_two.rev}/">{id_num_two.name}-{id_num_two.rev}.txt</a>',
            ),
            (
                f"{id_plus.name}",
                f'<a href="/doc/{id_plus.name}/">{id_plus.name}</a>',
            ),
            (
                f"{id_plus.name}-{id_plus.rev}.txt",
                f'<a href="/doc/{id_plus.name}/{id_plus.rev}/">{id_plus.name}-{id_plus.rev}.txt</a>',
            ),
            (
                f"{id_plus_end.name}",
                f'<a href="/doc/{id_plus_end.name}/">{id_plus_end.name}</a>',
            ),
            (
                f"{id_plus_end.name}-{id_plus_end.rev}.txt",
                f'<a href="/doc/{id_plus_end.name}/{id_plus_end.rev}/">{id_plus_end.name}-{id_plus_end.rev}.txt</a>',
            ),
            (
                f"{id_dot.name}",
                f'<a href="/doc/{id_dot.name}/">{id_dot.name}</a>',
            ),
            (
                f"{id_dot.name}-{id_dot.rev}.txt",
                f'<a href="/doc/{id_dot.name}/{id_dot.rev}/">{id_dot.name}-{id_dot.rev}.txt</a>',
            ),
        ]

        for input, output in cases:
            #debug.show("(urlize_ietf_docs(input),output)")
            self.assertEqual(urlize_ietf_docs(input), output)
