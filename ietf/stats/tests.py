import datetime

from pyquery import PyQuery

from django.urls import reverse as urlreverse

from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent
import ietf.stats.views

from ietf.submit.models import Submission
from ietf.doc.models import Document, DocAlias, State, RelatedDocument, NewRevisionDocEvent
from ietf.person.models import Person
from ietf.name.models import FormalLanguageName, DocRelationshipName

class StatisticsTests(TestCase):
    def test_stats_index(self):
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_document_stats(self):
        draft = make_test_data()

        # create some data for the statistics
        Submission.objects.create(
            authors=[ { "name": "Some Body", "email": "somebody@example.com", "affiliation": "Some Inc.", "country": "US" }],
            pages=30,
            rev=draft.rev,
            words=4000,
            draft=draft,
            file_types="txt",
            state_id="posted",
        )

        draft.formal_languages.add(FormalLanguageName.objects.get(slug="xml"))
        Document.objects.filter(pk=draft.pk).update(words=4000)
        # move it back so it shows up in the yearly summaries
        NewRevisionDocEvent.objects.filter(doc=draft, rev=draft.rev).update(
            time=datetime.datetime.now() - datetime.timedelta(days=500))

        referencing_draft = Document.objects.create(
            name="draft-ietf-mars-referencing",
            type_id="draft",
            title="Referencing",
            stream_id="ietf",
            abstract="Test",
            rev="00",
            pages=2,
            words=100
            )
        referencing_draft.set_state(State.objects.get(used=True, type="draft", slug="active"))
        DocAlias.objects.create(document=referencing_draft, name=referencing_draft.name)
        RelatedDocument.objects.create(
            source=referencing_draft,
            target=draft.docalias_set.first(),
            relationship=DocRelationshipName.objects.get(slug="refinfo")
        )
        NewRevisionDocEvent.objects.create(
            type="new_revision",
            by=Person.objects.get(name="(System)"),
            doc=referencing_draft,
            desc="New revision available",
            rev=referencing_draft.rev,
            time=datetime.datetime.now() - datetime.timedelta(days=1000)
        )


        # check redirect
        url = urlreverse(ietf.stats.views.document_stats)

        authors_url = urlreverse(ietf.stats.views.document_stats, kwargs={ "stats_type": "authors" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(authors_url in r["Location"])

        # check various stats types
        for stats_type in ["authors", "pages", "words", "format", "formlang",
                           "author/documents", "author/affiliation", "author/country",
                           "author/continent", "author/citations", "author/hindex",
                           "yearly/affiliation", "yearly/country", "yearly/continent"]:
            for document_type in ["", "rfc", "draft"]:
                for time_choice in ["", "5y"]:
                    url = urlreverse(ietf.stats.views.document_stats, kwargs={ "stats_type": stats_type })
                    r = self.client.get(url, {
                        "type": document_type,
                        "time": time_choice,
                    })
                    self.assertEqual(r.status_code, 200)
                    q = PyQuery(r.content)
                    self.assertTrue(q('#chart'))
                    if not stats_type.startswith("yearly"):
                        self.assertTrue(q('table.stats-data'))

    def test_known_country_list(self):
        make_test_data()

        # check redirect
        url = urlreverse(ietf.stats.views.known_countries_list)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("United States" in unicontent(r))

    def test_review_stats(self):
        doc = make_test_data()
        review_req = make_review_data(doc)

        # check redirect
        url = urlreverse(ietf.stats.views.review_stats)

        login_testing_unauthorized(self, "secretary", url)

        completion_url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(completion_url in r["Location"])

        self.client.logout()
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(completion_url)
        self.assertEqual(r.status_code, 403)

        # check tabular
        self.client.login(username="secretary", password="secretary+password")
        for stats_type in ["completion", "results", "states"]:
            url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": stats_type })
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            if stats_type != "results":
                self.assertTrue(q('.review-stats td:contains("1")'))

        # check chart
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "time" })
        url += "?team={}".format(review_req.team.acronym)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.stats-time-graph'))

        # check reviewer level
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion", "acronym": review_req.team.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.review-stats td:contains("1")'))
