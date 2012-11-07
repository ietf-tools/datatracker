import datetime, os, shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.person.models import Person, Email
    from ietf.group.models import Group, GroupHistory, Role, GroupStateTransitions
    from ietf.doc.models import Document, State, WriteupDocEvent
    from ietf.name.models import DocTagName
        
class ManageDelegatesTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_delete_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)
        
        delegates = Role.objects.filter(name="delegate", group__acronym="mars")
        self.assertTrue(len(delegates) > 0)
        
        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=delete]')), len(delegates))

        # delete
        r = self.client.post(url,
                             dict(remove="1",
                                  delete=[d.pk for d in delegates]))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=delete]')), 0)
        self.assertEquals(Role.objects.filter(name="delegate", group__acronym="mars").count(), 0)
        
    def test_add_not_existing_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=email]')), 1)

        # add non-existing
        r = self.client.post(url,
                             dict(email="unknown@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("unknown@example.com" in r.content)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[type=submit][value*="Send email"]')), 1)

        # we get back a warning and offer to send email, do that
        mailbox_before = len(outbox)
        r = self.client.post(url,
                             dict(email="unknown@example.com",
                                  form_type="notexist"))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("Email sent" in r.content)
        self.assertEquals(len(outbox), mailbox_before + 3)
        
    def test_add_delegate(self):
        make_test_data()

        url = urlreverse('manage_delegates', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=email]')), 1)

        # add existing person
        history_before = GroupHistory.objects.filter(acronym="mars").count()
        r = self.client.post(url,
                             dict(email="plain@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("new delegate" in r.content)
        self.assertTrue(Email.objects.get(address="plain@example.com").person.plain_name() in r.content)
        self.assertEquals(Role.objects.filter(name="delegate", group__acronym="mars", email__address="plain@example.com").count(), 1)
        self.assertEquals(history_before + 1, GroupHistory.objects.filter(acronym="mars").count())


class ManageShepherdsTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_manage_shepherds(self):
        make_test_data()

        url = urlreverse('manage_shepherds', kwargs=dict(acronym="mars"))
        login_testing_unauthorized(self, "secretary", url)

        # setup test documents
        group = Group.objects.get(acronym="mars")

        from ietf.doc.models import Document
        common = dict(group=group,
                      ad=Person.objects.get(user__username="ad"),
                      type_id="draft")
        Document.objects.create(name="test-shepherd-no",
                                title="No shepherd",
                                shepherd=None,
                                **common)
        Document.objects.create(name="test-shepherd-me",
                                title="Shepherd me",
                                shepherd=Person.objects.get(user__username="secretary"),
                                **common)
        Document.objects.create(name="test-shepherd-other", title="Shepherd other",
                                shepherd=Person.objects.get(user__username="plain"),
                                **common)
        for d in Document.objects.filter(name__startswith="test-shepherd"):
            d.set_state(State.objects.get(type="draft", slug="active"))
        
        # get and make sure they are divided correctly
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('div#noshepherd a:contains("No shepherd")')), 1)
        self.assertEquals(len(q('div#mydocs a:contains("Shepherd me")')), 1)
        self.assertEquals(len(q('div#othershepherds a:contains("Shepherd other")')), 1)

    def test_set_shepherd(self):
        draft = make_test_data()

        url = urlreverse('doc_managing_shepherd', kwargs=dict(acronym="mars", name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][name=setme]')), 1)

        # set me
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(setme="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(draft.shepherd)
        self.assertEquals(draft.shepherd.user.username, "secretary")
        self.assertEquals(draft.docevent_set.count(), events_before + 1)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue(Person.objects.get(user__username="secretary").plain_name() in r.content)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][name=remove_shepherd]')), 1)
        
        # unassign
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(remove_shepherd="1"))
        self.assertEquals(r.status_code, 200)
        draft = Document.objects.get(name=draft.name)
        self.assertTrue(not draft.shepherd)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)
        
        # change to existing person
        events_before = draft.docevent_set.count()
        r = self.client.post(url,
                             dict(email="plain@example.com",
                                  form_type="single"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue("Shepherd assigned" in r.content)
        self.assertTrue(Email.objects.get(address="plain@example.com").person.plain_name() in r.content)
        self.assertEquals(draft.docevent_set.count(), events_before + 1)

class ManageWorkflowTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_manage_workflows(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")

        url = urlreverse('manage_workflow', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        state = State.objects.get(type="draft-stream-ietf", slug="wg-lc")
        self.assertTrue(state not in group.unused_states.all())

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q("form.set-state").find("input[name=state][value=%s]" % state.pk).parents("form").find("input[name=active][value=0]")), 1)

        # deactivate state
        r = self.client.post(url,
                             dict(action="setstateactive",
                                  state=state.pk,
                                  active="0"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q("form.set-state").find("input[name=state][value=%s]" % state.pk).parents("form").find("input[name=active][value=1]")), 1)
        group = Group.objects.get(acronym=group.acronym)
        self.assertTrue(state in group.unused_states.all())

        # change next states
        state = State.objects.get(type="draft-stream-ietf", slug="wg-doc")
        next_states = State.objects.filter(type=b"draft-stream-ietf", slug__in=["parked", "dead", "wait-wgw", 'sub-pub']).values_list('pk', flat=True)
        r = self.client.post(url,
                             dict(action="setnextstates",
                                  state=state.pk,
                                  next_states=next_states))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q("form.set-next-states").find("input[name=state][value=%s]" % state.pk).parents('form').find("input[name=next_states][checked=checked]")), len(next_states))
        transitions = GroupStateTransitions.objects.filter(group=group, state=state)
        self.assertEquals(len(transitions), 1)
        self.assertEquals(set(transitions[0].next_states.values_list("pk", flat=True)), set(next_states))

        # change them back to default
        next_states = state.next_states.values_list("pk", flat=True)
        r = self.client.post(url,
                             dict(action="setnextstates",
                                  state=state.pk,
                                  next_states=next_states))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        transitions = GroupStateTransitions.objects.filter(group=group, state=state)
        self.assertEquals(len(transitions), 0)

        # deactivate tag
        tag = DocTagName.objects.get(slug="w-expert")
        r = self.client.post(url,
                             dict(action="settagactive",
                                  tag=tag.pk,
                                  active="0"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form').find('input[name=tag][value="%s"]' % tag.pk).parents("form").find("input[name=active]")), 1)
        group = Group.objects.get(acronym=group.acronym)
        self.assertTrue(tag in group.unused_tags.all())

class ManageWriteupTestCase(django.test.TestCase):
    fixtures = ['names']

    def test_manage_writeup(self):
        draft = make_test_data()

        self.assertTrue(not draft.tags.filter(slug="sheph-u"))

        url = urlreverse('doc_managing_writeup', kwargs=dict(acronym=draft.group.acronym, name=draft.name))
        r = self.client.get(url)
        self.client.login(remote_user="secretary")

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q("input[type=submit][value*=Change]")), 1)

        # post text
        r = self.client.post(url,
                             dict(writeup="New writeup"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q("input[name=followup]")), 1)
        self.assertEquals(len(q("input[name=confirm]")), 1)
        self.assertEquals(q("input[name=writeup]").val(), "New writeup")

        # update tag and confirm
        r = self.client.post(url,
                             dict(writeup="New writeup",
                                  confirm="1",
                                  followup="1",
                                  comment="Starting on write up",
                                  complete_tag="Modify"))
        self.assertEquals(r.status_code, 200)
        e = draft.latest_event(WriteupDocEvent, type="changed_protocol_writeup")
        self.assertTrue(e)
        self.assertEquals(e.text, "New writeup")
        self.assertEquals(e.by.user.username, "secretary")
        self.assertFalse(draft.tags.filter(slug="sheph-u"))


if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del ManageDelegatesTestCase 
    del ManageShepherdsTestCase 
    del ManageWorkflowTestCase
    del ManageWriteupCase
