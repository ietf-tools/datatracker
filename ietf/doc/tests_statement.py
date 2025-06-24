# Copyright The IETF Trust 2023-2025, All Rights Reserved

import debug  # pyflakes:ignore

from pyquery import PyQuery

from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse

from ietf.doc.factories import StatementFactory, DocEventFactory
from ietf.doc.models import Document, State, NewRevisionDocEvent
from ietf.doc.storage_utils import retrieve_str
from ietf.group.models import Group
from ietf.person.factories import PersonFactory
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import (
    TestCase,
    reload_db_objects,
    login_testing_unauthorized,
)


class StatementsTestCase(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        "DOCUMENT_PATH_PATTERN"
    ]

    def extract_content(self, response):
        if not hasattr(response, "_cached_extraction"):
            response._cached_extraction = list(response.streaming_content)[0].decode(
                "utf-8"
            )
        return response._cached_extraction

    def write_statement_markdown_file(self, statement):
        (
            Path(settings.DOCUMENT_PATH_PATTERN.format(doc=statement))
            / ("%s-%s.md" % (statement.name, statement.rev))
        ).write_text(
            """# This is a test statement.
Version: {statement.rev}

## A section

This test section has some text.
"""
        )

    def write_statement_pdf_file(self, statement):
        (
            Path(settings.DOCUMENT_PATH_PATTERN.format(doc=statement))
            / ("%s-%s.pdf" % (statement.name, statement.rev))
        ).write_text(
            f"{statement.rev} This is not valid PDF, but the test does not need it to be"
        )

    def test_statement_doc_view(self):
        doc = StatementFactory()
        self.write_statement_markdown_file(doc)
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-state").text(), "Active")
        self.assertEqual(q("#statement-type").text(), "IAB Statement")
        self.assertIn("has some text", q(".card-body").text())
        published = doc.docevent_set.filter(type="published_statement").last().time
        self.assertIn(
            published.astimezone(ZoneInfo(settings.TIME_ZONE)).date().isoformat(),
            q("#published").text(),
        )

        doc.set_state(State.objects.get(type_id="statement", slug="replaced"))
        doc2 = StatementFactory()
        doc2.relateddocument_set.create(relationship_id="replaces", target=doc)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-state").text(), "Replaced")
        self.assertEqual(q("#statement-type").text(), "Replaced IAB Statement")
        self.assertEqual(q("#statement-type").next().text(), f"Replaced by {doc2.name}")

        url = urlreverse(
            "ietf.doc.views_doc.document_main", kwargs=dict(name=doc2.name)
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#statement-type").text(), "IAB Statement")
        self.assertEqual(q("#statement-type").next().text(), f"Replaces {doc.name}")

    def test_serve_pdf(self):
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf",
            kwargs=dict(name="statement-does-not-exist"),
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        doc = StatementFactory()
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name)
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)  # File not found

        self.write_statement_pdf_file(doc)
        doc.rev = "01"
        e = DocEventFactory(type="published_statement", doc=doc, rev=doc.rev)
        doc.save_with_history([e])
        self.write_statement_pdf_file(doc)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get("Content-Type"), "application/pdf")
        self.assertTrue(
            self.extract_content(r).startswith(doc.rev)
        )  # relies on test doc not actually being pdf

        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name, rev="00")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.extract_content(r).startswith("00 "))
        url = urlreverse(
            "ietf.doc.views_statement.serve_pdf", kwargs=dict(name=doc.name, rev="01")
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.extract_content(r).startswith("01 "))

    def test_submit(self):
        doc = StatementFactory()
        url = urlreverse("ietf.doc.views_statement.submit", kwargs=dict(name=doc.name))

        rev = doc.rev
        r = self.client.post(
            url, {"statement_submission": "enter", "statement_content": "# oiwefrase"}
        )
        self.assertEqual(r.status_code, 302)
        doc = reload_db_objects(doc)
        self.assertEqual(rev, doc.rev)

        nobody = PersonFactory()
        self.client.login(
            username=nobody.user.username, password=nobody.user.username + "+password"
        )
        r = self.client.post(
            url, {"statement_submission": "enter", "statement_content": "# oiwefrase"}
        )
        self.assertEqual(r.status_code, 403)
        doc = reload_db_objects(doc)
        self.assertEqual(rev, doc.rev)
        self.client.logout()

        for username in ["secretary"]:  # There is potential for expanding this list
            self.client.login(username=username, password=username + "+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            file = SimpleUploadedFile(
                "random.pdf",
                b"not valid pdf",
                content_type="application/pdf",
            )
            for postdict in [
                {
                    "statement_submission": "enter",
                    "statement_content": f"# {username}",
                },
                {
                    "statement_submission": "upload",
                    "statement_file": file,
                },
            ]:
                docevent_count = doc.docevent_set.count()
                empty_outbox()
                r = self.client.post(url, postdict)
                self.assertEqual(r.status_code, 302)
                doc = reload_db_objects(doc)
                self.assertEqual("%02d" % (int(rev) + 1), doc.rev)
                if postdict["statement_submission"] == "enter":
                    self.assertEqual(f"# {username}", doc.text())
                    self.assertEqual(
                        retrieve_str("statement", f"{doc.name}-{doc.rev}.md"),
                        f"# {username}"
                    )
                else:
                    self.assertEqual("not valid pdf", doc.text())
                    self.assertEqual(
                        retrieve_str("statement", f"{doc.name}-{doc.rev}.pdf"),
                        "not valid pdf"
                    )
                self.assertEqual(docevent_count + 1, doc.docevent_set.count())
                self.assertEqual(0, len(outbox))
                rev = doc.rev
            self.client.logout()

    def test_start_new_statement(self):
        url = urlreverse("ietf.doc.views_statement.new_statement")
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(
            r,
            "Replace this with the content of the statement in markdown source",
            status_code=200,
        )
        group = Group.objects.get(acronym="iab")
        r = self.client.post(
            url,
            dict(
                group=group.pk,
                title="default",
                statement_submission="enter",
                statement_content=render_to_string(
                    "doc/statement/statement_template.md", {"settings": settings}
                ),
            ),
        )
        self.assertContains(r, "The example content may not be saved.", status_code=200)

        file = SimpleUploadedFile(
            "random.pdf",
            b"not valid pdf",
            content_type="application/pdf",
        )
        group = Group.objects.get(acronym="iab")
        for postdict in [
            dict(
                group=group.pk,
                title="title one",
                statement_submission="enter",
                statement_content="some stuff",
            ),
            dict(
                group=group.pk,
                title="title two",
                statement_submission="upload",
                statement_file=file,
            ),
        ]:
            empty_outbox()
            r = self.client.post(url, postdict)
            self.assertEqual(r.status_code, 302)
            name = f"statement-{group.acronym}-{postdict['title']}".replace(
                " ", "-"
            )  # cheap slugification
            statement = Document.objects.filter(
                name=name, type_id="statement"
            ).first()
            self.assertIsNotNone(statement)
            self.assertEqual(statement.title, postdict["title"])
            self.assertEqual(statement.rev, "00")
            self.assertEqual(statement.get_state_slug(), "active")
            self.assertEqual(
                statement.latest_event(NewRevisionDocEvent).rev, "00"
            )
            self.assertIsNotNone(statement.latest_event(type="published_statement"))
            self.assertIsNotNone(statement.history_set.last().latest_event(type="published_statement"))
            if postdict["statement_submission"] == "enter":
                self.assertEqual(statement.text_or_error(), "some stuff")
                self.assertEqual(
                    retrieve_str("statement", statement.uploaded_filename),
                    "some stuff"
                )
            else:
                self.assertTrue(statement.uploaded_filename.endswith("pdf"))
                self.assertEqual(
                    retrieve_str("statement", f"{statement.name}-{statement.rev}.pdf"),
                    "not valid pdf"
                )
            self.assertEqual(len(outbox), 0)

        existing_statement = StatementFactory()
        for postdict in [
            dict(
                group=group.pk,
                title="",
                statement_submission="enter",
                statement_content="some stuff",
            ),
            dict(
                group=group.pk,
                title="a title",
                statement_submission="enter",
                statement_content="",
            ),
            dict(
                group=group.pk,
                title=existing_statement.title,
                statement_submission="enter",
                statement_content="some stuff",
            ),
            dict(
                group=group.pk,
                title="森川",
                statement_submission="enter",
                statement_content="some stuff",
            ),
            dict(
                group=group.pk,
                title="a title",
                statement_submission="",
                statement_content="some stuff",
            ),
            dict(
                group="",
                title="a title",
                statement_submission="enter",
                statement_content="some stuff",
            ),
            dict(
                group=0,
                title="a title",
                statement_submission="enter",
                statement_content="some stuff",
            ),
        ]:
            r = self.client.post(url, postdict)
            self.assertEqual(r.status_code, 200, f"Wrong status_code for {postdict}")
            q = PyQuery(r.content)
            self.assertTrue(
                q("form div.is-invalid"), f"Expected an error for {postdict}"
            )

    def test_submit_non_markdown_formats(self):
        doc = StatementFactory()

        file = SimpleUploadedFile(
            "random.pdf",
            b"01 This is not valid PDF, but the test does not need it to be",
            content_type="application/pdf",
        )

        url = urlreverse("ietf.doc.views_statement.submit", kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.post(
            url,
            {
                "statement_submission": "upload",
                "statement_file": file,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            r["Location"],
            urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc.name)),
        )

        doc = reload_db_objects(doc)
        self.assertEqual(doc.rev, "01")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(
            q("#id_statement_content").text().strip(),
            "The current revision of this statement is in pdf format",
        )

        file = SimpleUploadedFile(
            "random.mp4", b"29ucdvn2o09hano5", content_type="video/mp4"
        )
        r = self.client.post(
            url, {"statement_submission": "upload", "statement_file": file}
        )
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Unexpected content" in q("#id_statement_file").next().text())

    def test_change_statement_state(self):
        statement = StatementFactory()  # starts in "active" state
        active_state = State.objects.get(type_id="statement", slug="active")
        replaced_state = State.objects.get(type_id="statement", slug="replaced")
        url = urlreverse(
            "ietf.doc.views_statement.change_statement_state",
            kwargs={"name": statement.name},
        )

        events_before = statement.docevent_set.count()
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)

        r = self.client.post(url, {"state": active_state.pk}, follow=True)
        self.assertContains(r, "State not changed", status_code=200)
        statement = Document.objects.get(pk=statement.pk)  # bust the state cache
        self.assertEqual(statement.get_state(), active_state)

        r = self.client.post(url, {"state": replaced_state.pk}, follow=True)
        self.assertContains(r, "State changed to", status_code=200)
        statement = Document.objects.get(pk=statement.pk)  # bust the state cache
        self.assertEqual(statement.get_state(), replaced_state)

        events_after = statement.docevent_set.count()
        self.assertEqual(events_after, events_before + 1)
        event = statement.docevent_set.first()
        self.assertEqual(event.type, "changed_state")
        self.assertEqual(
            event.desc, "Statement State changed to <b>Replaced</b> from Active"
        )
