import datetime
import sys
if sys.version_info[0] == 2 and sys.version_info[1] < 7:
    import unittest2 as unittest
else:
    import unittest
from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import ( Document, DocAlias, DocRelationshipName, RelatedDocument, State,
    DocEvent, BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent, save_document_in_history )
from ietf.group.models import Group
from ietf.person.models import Person
from ietf.utils.mail import outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_utils import TestCase

class SearchTestCase(TestCase):
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

    def test_frontpage(self):
        make_test_data()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Search Internet-Drafts" in r.content)

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

    def test_document_primary_and_history_views(self):
        make_test_data()

        # Ensure primary views of both current and historic versions of documents works
        for docname in ["draft-imaginary-independent-submission",
                        "conflict-review-imaginary-irtf-submission",
                        "status-change-imaginary-mid-review",
                        "charter-ietf-mars",
                        "agenda-42-mars",
                        "minutes-42-mars",
                        "slides-42-mars-1",
                       ]:
            doc = Document.objects.get(name=docname)
            # give it some history
            save_document_in_history(doc)
            doc.rev="01"
            doc.save()

            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
            self.assertEqual(r.status_code, 200)
            self.assertTrue("%s-01"%docname in r.content)
    
            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name,rev="01")))
            self.assertEqual(r.status_code, 302)
     
            r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name,rev="00")))
            self.assertEqual(r.status_code, 200)
            self.assertTrue("%s-00"%docname in r.content)

    def test_document_charter(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name="charter-ietf-mars")))
        self.assertEqual(r.status_code, 200)

    def test_document_conflict_review(self):
        make_test_data()

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name='conflict-review-imaginary-irtf-submission')))
        self.assertEqual(r.status_code, 200)

    def test_document_material(self):
        draft = make_test_data()

        doc = Document.objects.create(
            name="slides-testteam-test-slides",
            rev="00",
            title="Test Slides",
            group=draft.group,
            type_id="slides"
        )
        doc.set_state(State.objects.get(type="slides", slug="active"))
        DocAlias.objects.create(name=doc.name, document=doc)

        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)

    def test_document_ballot(self):
        doc = make_test_data()
        ballot = doc.active_ballot()

        pos = BallotPositionDocEvent.objects.create(
            doc=doc,
            ballot=ballot,
            type="changed_ballot_position",
            pos_id="yes",
            comment="Looks fine to me",
            comment_time=datetime.datetime.now(),
            ad=Person.objects.get(user__username="ad"),
            by=Person.objects.get(name="(System)"))

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(pos.comment in r.content)

        # test with ballot_id
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(pos.comment in r.content)

        # test popup too while we're at it
        r = self.client.get(urlreverse("ietf.doc.views_doc.ballot_popup", kwargs=dict(name=doc.name, ballot_id=ballot.pk)))
        self.assertEqual(r.status_code, 200)
        
    def test_document_ballot_needed_positions(self):
        make_test_data()

        # draft
        doc = Document.objects.get(name='draft-ietf-mars-test')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertTrue('more YES or NO' in r.content)
        Document.objects.filter(pk=doc.pk).update(intended_std_level='inf')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertFalse('more YES or NO' in r.content)

        # status change
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        self.client.login(username='ad', password='ad+password')
        r = self.client.post(urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name)),dict(new_state=iesgeval_pk))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(r._headers["location"][1])
        self.assertTrue(">IESG Evaluation<" in r.content)

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9998'),relationship_id='tohist')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertFalse('Needs a YES' in r.content)
        self.assertFalse('more YES or NO' in r.content)

        doc.relateddocument_set.create(target=DocAlias.objects.get(name='rfc9999'),relationship_id='tois')
        r = self.client.get(urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name)))
        self.assertTrue('more YES or NO' in r.content)

    def test_document_json(self):
        doc = make_test_data()

        r = self.client.get(urlreverse("ietf.doc.views_doc.document_json", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)

    def test_writeup(self):
        doc = make_test_data()

        appr = WriteupDocEvent.objects.create(
            doc=doc,
            desc="Changed text",
            type="changed_ballot_approval_text",
            text="This is ballot approval text.",
            by=Person.objects.get(name="(System)"))

        notes = WriteupDocEvent.objects.create(
            doc=doc,
            desc="Changed text",
            type="changed_ballot_writeup_text",
            text="This is ballot writeup notes.",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('doc_writeup', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(appr.text in r.content)
        self.assertTrue(notes.text in r.content)

    def test_history(self):
        doc = make_test_data()

        e = DocEvent.objects.create(
            doc=doc,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('doc_history', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(e.desc in r.content)
        
    def test_document_feed(self):
        doc = make_test_data()

        e = DocEvent.objects.create(
            doc=doc,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/document-changes/%s/" % doc.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(e.desc in r.content)

    def test_last_call_feed(self):
        doc = make_test_data()

        doc.set_state(State.objects.get(type="draft-iesg", slug="lc"))

        LastCallDocEvent.objects.create(
            doc=doc,
            desc="Last call",
            type="sent_last_call",
            by=Person.objects.get(user__username="secretary"),
            expires=datetime.date.today() + datetime.timedelta(days=7))

        r = self.client.get("/feed/last-call/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(doc.name in r.content)

    def test_state_help(self):
        url = urlreverse('state_help', kwargs=dict(type="draft-iesg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(State.objects.get(type="draft-iesg", slug="lc").name in r.content)

    def test_document_nonietf_pubreq_button(self):
        doc = make_test_data()

        self.client.login(username='iab-chair', password='iab-chair+password')
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q('.actions'))

        Document.objects.filter(pk=doc.pk).update(stream='iab')
        r = self.client.get(urlreverse("doc_view", kwargs=dict(name=doc.name)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue('IESG state' in q('.actions').html())


class AddCommentTestCase(TestCase):
    def test_add_comment(self):
        draft = make_test_data()
        url = urlreverse('doc_add_comment', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=comment]')), 1)

        # request resurrect
        events_before = draft.docevent_set.count()
        mailbox_before = len(outbox)
        
        r = self.client.post(url, dict(comment="This is a test."))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(draft.docevent_set.count(), events_before + 1)
        self.assertEqual("This is a test.", draft.latest_event().desc)
        self.assertEqual("added_comment", draft.latest_event().type)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("updated" in outbox[-1]['Subject'])
        self.assertTrue(draft.name in outbox[-1]['Subject'])

        # Make sure we can also do it as IANA
        self.client.login(username="iana", password="iana+password")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=comment]')), 1)


class TemplateTagTest(unittest.TestCase):
    def test_template_tags(self):
        import doctest
        from ietf.doc.templatetags import ietf_filters
        failures, tests = doctest.testmod(ietf_filters)
        self.assertEqual(failures, 0)

class ReferencesTest(TestCase):
    perma_fixtures = ['names']

    def test_references(self):
        make_test_data()
        doc1 = Document.objects.get(name='draft-ietf-mars-test')
        doc2 = DocAlias.objects.get(name='draft-imaginary-independent-submission')
        RelatedDocument.objects.get_or_create(source=doc1,target=doc2,relationship=DocRelationshipName.objects.get(slug='refnorm'))
        url = urlreverse('doc_references', kwargs=dict(name=doc1.name))
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(doc2.name in r.content)
        url = urlreverse('doc_referenced_by', kwargs=dict(name=doc2.name))
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(doc1.name in r.content)
       
