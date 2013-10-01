import os, shutil, datetime

from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

from ietf.utils.mail import outbox
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils import TestCase

from ietf.doc.models import *
from ietf.name.models import *
from ietf.group.models import *
from ietf.person.models import *
from ietf.meeting.models import Meeting, MeetingTypeName
from ietf.iesg.models import TelechatDate

# extra tests
from ietf.doc.tests_draft import *
from ietf.doc.tests_ballot import *
from ietf.doc.tests_conflict_review import *
from ietf.doc.tests_status_change import *


class SearchTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_search(self):
        draft = make_test_data()

        base_url = urlreverse("doc_search")

        # only show form, no search yet
        r = self.client.get(base_url)
        self.assertEqual(r.status_code, 200)

        # no match
        r = self.client.get(base_url + "?activedrafts=on&name=thisisnotadocumentname")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in str(r.content).lower())

        r = self.client.get(base_url + "?rfcs=on&name=xyzzy")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in r.content.lower())

        r = self.client.get(base_url + "?olddrafts=on&name=")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("no documents match" in r.content.lower())

        # find by rfc/active/inactive
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        r = self.client.get(base_url + "?rfcs=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        draft.set_state(State.objects.get(type="draft", slug="active"))
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        draft.set_state(State.objects.get(type="draft", slug="expired"))
        r = self.client.get(base_url + "?olddrafts=on&name=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)
        
        draft.set_state(State.objects.get(type="draft", slug="active"))

        # find by title
        r = self.client.get(base_url + "?activedrafts=on&name=%s" % draft.title.split()[0])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by author
        r = self.client.get(base_url + "?activedrafts=on&by=author&author=%s" % draft.authors.all()[0].person.name_parts()[1])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by group
        r = self.client.get(base_url + "?activedrafts=on&by=group&group=%s" % draft.group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by area
        r = self.client.get(base_url + "?activedrafts=on&by=area&area=%s" % draft.group.parent_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by AD
        r = self.client.get(base_url + "?activedrafts=on&by=ad&ad=%s" % draft.ad_id)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        # find by IESG state
        r = self.client.get(base_url + "?activedrafts=on&by=state&state=%s&substate=" % draft.get_state("draft-iesg").pk)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

    def test_drafts_pages(self):
        draft = make_test_data()

        r = self.client.get(urlreverse("docs_for_ad", kwargs=dict(name=draft.ad.full_name_as_key())))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)

        draft.set_state(State.objects.get(type="draft-iesg", slug="lc"))
        r = self.client.get(urlreverse("drafts_in_last_call"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)
        
    def test_indexes(self):
        draft = make_test_data()

        r = self.client.get(urlreverse("index_all_drafts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in r.content)

        r = self.client.get(urlreverse("index_active_drafts"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.title in r.content)
        

class DocTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_document_draft(self):
        draft = make_test_data()

        # these tests aren't testing all attributes yet, feel free to
        # expand them


        # active draft
        draft.set_state(State.objects.get(type="draft", slug="active"))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active Internet-Draft" in r.content)

        # expired draft
        draft.set_state(State.objects.get(type="draft", slug="expired"))

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Expired Internet-Draft" in r.content)

        # replaced draft
        draft.set_state(State.objects.get(type="draft", slug="repl"))

        replacement = Document.objects.create(
            name="draft-ietf-replacement",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Replacement Draft",
            stream_id=draft.stream_id, group_id=draft.group_id, abstract=draft.stream, rev=draft.rev,
            pages=draft.pages, intended_std_level_id=draft.intended_std_level_id,
            shepherd_id=draft.shepherd_id, ad_id=draft.ad_id, expires=draft.expires,
            notify=draft.notify, note=draft.note)
        DocAlias.objects.create(name=replacement.name, document=replacement)
        rel = RelatedDocument.objects.create(source=replacement,
                                             target=draft.docalias_set.get(name__startswith="draft"),
                                             relationship_id="replaces")

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Replaced Internet-Draft" in r.content)
        self.assertTrue(replacement.name in r.content)
        rel.delete()

        # draft published as RFC
        draft.set_state(State.objects.get(type="draft", slug="rfc"))
        draft.std_level_id = "bcp"
        draft.save()

        DocEvent.objects.create(doc=draft, type="published_rfc", by=Person.objects.get(name="(System)"))

        rfc_alias = DocAlias.objects.create(name="rfc123456", document=draft)
        bcp_alias = DocAlias.objects.create(name="bcp123456", document=draft)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=draft.name)))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=bcp_alias.name)))
        self.assertEqual(r.status_code, 302)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=rfc_alias.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("RFC 123456" in r.content)
        self.assertTrue(draft.name in r.content)

        # naked RFC
        rfc = Document.objects.create(
            name="rfc1234567",
            type_id="draft",
            title="RFC without a Draft",
            stream_id="ise",
            group=Group.objects.get(type="individ"),
            std_level_id="ps")
        DocAlias.objects.create(name=rfc.name, document=rfc)
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=rfc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("RFC 1234567" in r.content)

        # unknown draft
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name="draft-xyz123")))
        self.assertEqual(r.status_code, 404)

    def test_document_charter(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name="charter-ietf-mars")))
        self.assertEqual(r.status_code, 200)

    def test_document_conflict_review(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name='conflict-review-imaginary-irtf-submission')))
        self.assertEqual(r.status_code, 200)

    def test_document_ballot(self):
        doc = make_test_data()
        ballot = doc.active_ballot()

        BallotPositionDocEvent.objects.create(
            doc=doc,
            type="changed_ballot_position",
            pos_id="yes",
            comment="Looks fine to me",
            comment_time=datetime.datetime.now(),
            ad=Person.objects.get(user__username="ad"),
            by=Person.objects.get(name="(System)"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)

        # test popup too while we're at it
        r = self.client.get(urlreverse("ietf.doc.views_doc.ballot_popup", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)
        
    def test_document_json(self):
        doc = make_test_data()

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_json", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)


class AddCommentTestCase(TestCase):
    # See ietf.utils.test_utils.TestCase for the use of perma_fixtures vs. fixtures
    perma_fixtures = ['names']

    def test_add_comment(self):
        draft = make_test_data()
        url = urlreverse('doc_add_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)

        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(comment="This is a test."))
        self.assertEquals(r.status_code, 302)

        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        self.assertEquals("This is a test.", draft.latest_event().desc)
        self.assertEquals("added_comment", draft.latest_event().type)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("updated" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

        # Make sure we can also do it as IANA
        self.client.login(remote_user="iana")

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=comment]')), 1)


class TemplateTagTest(unittest.TestCase):
    def test_template_tags(self):
        import doctest
        from ietf.doc.templatetags import ietf_filters
        failures, tests = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)
