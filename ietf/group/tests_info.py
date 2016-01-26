# -*- coding: utf-8 -*-
import os
import shutil
import calendar
import datetime
import json

from pyquery import PyQuery
from tempfile import NamedTemporaryFile
import debug                            # pyflakes:ignore

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.core.urlresolvers import NoReverseMatch

from ietf.doc.models import Document, DocAlias, DocEvent, State
from ietf.group.models import Group, GroupEvent, GroupMilestone, GroupStateTransitions 
from ietf.group.utils import save_group_in_history
from ietf.name.models import DocTagName, GroupStateName, GroupTypeName
from ietf.person.models import Person, Email
from ietf.utils.test_utils import TestCase, unicontent
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.group.factories import GroupFactory
from ietf.meeting.factories import SessionFactory

class GroupPagesTests(TestCase):
    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_active_groups(self):
        draft = make_test_data()
        group = draft.group

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(group.parent.name in unicontent(r))
        self.assertTrue(group.acronym in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(group.ad_role().person.plain_name() in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="rg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('Active research groups' in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="area"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Far Future (farfut)" in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="ag"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active area groups" in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="dir"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active directorates" in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type="team"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Active teams" in unicontent(r))

        url = urlreverse('ietf.group.info.active_groups', kwargs=dict())
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Directorate" in unicontent(r))
        self.assertTrue("AG" in unicontent(r))

        for slug in GroupTypeName.objects.exclude(slug__in=['wg','rg','ag','area','dir','team']).values_list('slug',flat=True):
            with self.assertRaises(NoReverseMatch):
                url=urlreverse('ietf.group.info.active_groups', kwargs=dict(group_type=slug))

    def test_wg_summaries(self):
        draft = make_test_data()
        group = draft.group

        chair = Email.objects.filter(role__group=group, role__name="chair")[0]

        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")

        url = urlreverse('ietf.group.info.wg_summary_area', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(group.parent.name in unicontent(r))
        self.assertTrue(group.acronym in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(chair.address in unicontent(r))

        url = urlreverse('ietf.group.info.wg_summary_acronym', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(group.acronym in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(chair.address in unicontent(r))
        
        url = urlreverse('ietf.group.info.wg_charters', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(group.acronym in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(group.ad_role().person.plain_name() in unicontent(r))
        self.assertTrue(chair.address in unicontent(r))
        self.assertTrue("This is a charter." in unicontent(r))

        url = urlreverse('ietf.group.info.wg_charters_by_acronym', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(group.acronym in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(group.ad_role().person.plain_name() in unicontent(r))
        self.assertTrue(chair.address in unicontent(r))
        self.assertTrue("This is a charter." in unicontent(r))

    def test_chartering_groups(self):
        draft = make_test_data()
        group = draft.group
        group.charter.set_state(State.objects.get(used=True, type="charter", slug="intrev"))

        url = urlreverse('ietf.group.info.chartering_groups')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)

    def test_concluded_groups(self):
        draft = make_test_data()
        group = draft.group
        group.state = GroupStateName.objects.get(used=True, slug="conclude")
        group.save()

        url = urlreverse('ietf.group.info.concluded_groups')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)

    def test_bofs(self):
        draft = make_test_data()
        group = draft.group
        group.state_id = "bof"
        group.save()

        url = urlreverse('ietf.group.info.bofs', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)
        
    def test_group_documents(self):
        draft = make_test_data()
        group = draft.group

        draft2 = Document.objects.create(
            name="draft-somebody-mars-test",
            time=datetime.datetime.now(),
            type_id="draft",
            title="Test By Somebody",
            stream_id="ietf",
            group=Group.objects.get(type="individ"),
            abstract="Abstract.",
            rev="01",
            pages=2,
            intended_std_level_id="ps",
            shepherd=None,
            ad=None,
            expires=datetime.datetime.now() + datetime.timedelta(days=10),
            notify="",
            note="",
            )

        draft2.set_state(State.objects.get(used=True, type="draft", slug="active"))
        DocAlias.objects.create(
            document=draft2,
            name=draft2.name,
            )

        url = urlreverse('ietf.group.info.group_documents', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))
        self.assertTrue(group.name in unicontent(r))
        self.assertTrue(group.acronym in unicontent(r))

        self.assertTrue(draft2.name in unicontent(r))

        # Make sure that a logged in user is presented with an opportunity to add results to their community list
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue(any([draft2.name in x.attrib['href'] for x in q('table td a.community-list-add-remove-doc')]))

        # test the txt version too while we're at it
        url = urlreverse('ietf.group.info.group_documents_txt', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))
        self.assertTrue(draft2.name in unicontent(r))

    def test_group_charter(self):
        draft = make_test_data()
        group = draft.group

        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")

        milestone = GroupMilestone.objects.create(
            group=group,
            state_id="active",
            desc="Get Work Done",
            due=datetime.date.today() + datetime.timedelta(days=100))
        milestone.docs.add(draft)

        for url in [group.about_url(),
                    urlreverse('ietf.group.info.group_about',kwargs=dict(acronym=group.acronym)),
                    urlreverse('ietf.group.info.group_about',kwargs=dict(acronym=group.acronym,group_type=group.type_id)),
                   ]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(group.name in unicontent(r))
            self.assertTrue(group.acronym in unicontent(r))
            self.assertTrue("This is a charter." in unicontent(r))
            self.assertTrue(milestone.desc in unicontent(r))
            self.assertTrue(milestone.docs.all()[0].name in unicontent(r))

    def test_group_about(self):
        make_test_data()
        group = Group.objects.create(
            type_id="team",
            acronym="testteam",
            name="Test Team",
            description="The test team is testing.",
            state_id="active",
        )

        for url in [group.about_url(),
                    urlreverse('ietf.group.info.group_about',kwargs=dict(acronym=group.acronym)),
                    urlreverse('ietf.group.info.group_about',kwargs=dict(acronym=group.acronym,group_type=group.type_id)),
                   ]:
            url = group.about_url()
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(group.name in unicontent(r))
            self.assertTrue(group.acronym in unicontent(r))
            self.assertTrue(group.description in unicontent(r))

    def test_materials(self):
        make_test_data()
        group = Group.objects.create(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        doc = Document.objects.create(
            name="slides-testteam-test-slides",
            rev="00",
            title="Test Slides",
            group=group,
            type_id="slides",
        )
        doc.set_state(State.objects.get(type="slides", slug="active"))
        DocAlias.objects.create(name=doc.name, document=doc)

        for url in [ urlreverse("group_materials", kwargs={ 'acronym': group.acronym }),
                     urlreverse("group_materials", kwargs={ 'acronym': group.acronym , 'group_type': group.type_id}),
                   ]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(doc.title in unicontent(r))
            self.assertTrue(doc.name in unicontent(r))

        url =  urlreverse("group_materials", kwargs={ 'acronym': group.acronym })

        # try deleting the document and check it's gone
        doc.set_state(State.objects.get(type="slides", slug="deleted"))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(doc.title not in unicontent(r))

    def test_history(self):
        draft = make_test_data()
        group = draft.group

        e = GroupEvent.objects.create(
            group=group,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        url = urlreverse('ietf.group.info.history', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(e.desc in unicontent(r))

    def test_feed(self):
        draft = make_test_data()
        group = draft.group

        ge = GroupEvent.objects.create(
            group=group,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        de = DocEvent.objects.create(
            doc=group.charter,
            desc="Something else happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/group-changes/%s/" % group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ge.desc in unicontent(r))
        self.assertTrue(de.desc in unicontent(r))


class GroupEditTests(TestCase):
    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_create(self):
        make_test_data()

        url = urlreverse('group_create', kwargs=dict(group_type="wg"))
        login_testing_unauthorized(self, "secretary", url)

        num_wgs = len(Group.objects.filter(type="wg"))

        bof_state = GroupStateName.objects.get(slug="bof")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=acronym]')), 1)

        # faulty post
        r = self.client.post(url, dict(acronym="foobarbaz")) # No name
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        self.assertEqual(len(Group.objects.filter(type="wg")), num_wgs)

        # acronym contains non-alphanumeric
        r = self.client.post(url, dict(acronym="test...", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)

        # acronym contains hyphen
        r = self.client.post(url, dict(acronym="test-wg", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)

        # acronym too short
        r = self.client.post(url, dict(acronym="t", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)

        # acronym doesn't start with an alpha character
        r = self.client.post(url, dict(acronym="1startwithalpha", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)

        # creation
        r = self.client.post(url, dict(acronym="testwg", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(Group.objects.filter(type="wg")), num_wgs + 1)
        group = Group.objects.get(acronym="testwg")
        self.assertEqual(group.name, "Testing WG")
        self.assertEqual(group.charter.name, "charter-ietf-testwg")
        self.assertEqual(group.charter.rev, "00-00")

    def test_create_rg(self):

        make_test_data()

        url = urlreverse('group_create', kwargs=dict(group_type="rg"))
        login_testing_unauthorized(self, "secretary", url)

        irtf = Group.objects.get(acronym='irtf')
        num_rgs = len(Group.objects.filter(type="rg"))

        proposed_state = GroupStateName.objects.get(slug="proposed")

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=acronym]')), 1)
        self.assertEqual(q('form input[name=parent]').attr('value'),'%s'%irtf.pk)

        r = self.client.post(url, dict(acronym="testrg", name="Testing RG", state=proposed_state.pk, parent=irtf.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(Group.objects.filter(type="rg")), num_rgs + 1)
        group = Group.objects.get(acronym="testrg")
        self.assertEqual(group.name, "Testing RG")
        self.assertEqual(group.charter.name, "charter-irtf-testrg")
        self.assertEqual(group.charter.rev, "00-00")
        self.assertEqual(group.parent.acronym,'irtf')

    def test_create_based_on_existing_bof(self):
        make_test_data()

        url = urlreverse('group_create', kwargs=dict(group_type="wg"))
        login_testing_unauthorized(self, "secretary", url)

        group = Group.objects.get(acronym="mars")

        # try hijacking area - faulty
        r = self.client.post(url, dict(name="Test", acronym=group.parent.acronym))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        self.assertEqual(len(q('form input[name="confirm_acronym"]')), 0) # can't confirm us out of this

        # try elevating BoF to WG
        group.state_id = "bof"
        group.save()

        r = self.client.post(url, dict(name="Test", acronym=group.acronym))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        self.assertEqual(len(q('form input[name="confirm_acronym"]')), 1)

        self.assertEqual(Group.objects.get(acronym=group.acronym).state_id, "bof")

        # confirm elevation
        state = GroupStateName.objects.get(slug="proposed")
        r = self.client.post(url, dict(name="Test", acronym=group.acronym, confirm_acronym="1", state=state.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Group.objects.get(acronym=group.acronym).state_id, "proposed")
        self.assertEqual(Group.objects.get(acronym=group.acronym).name, "Test")

    def test_edit_info(self):
        make_test_data()
        group = Group.objects.get(acronym="mars")

        url = urlreverse('group_edit', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=parent]')), 1)
        self.assertEqual(len(q('form input[name=acronym]')), 1)

        # faulty post
        Group.objects.create(name="Collision Test Group", acronym="collide")
        r = self.client.post(url, dict(acronym="collide"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

        # create old acronym
        group.acronym = "oldmars"
        group.save()
        save_group_in_history(group)
        group.acronym = "mars"
        group.save()

        # post with warning
        r = self.client.post(url, dict(acronym="oldmars"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        
        # edit info
        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")
        area = group.parent
        ad = Person.objects.get(name="Areað Irector")
        state = GroupStateName.objects.get(slug="bof")
        empty_outbox()
        r = self.client.post(url,
                             dict(name="Mars Not Special Interest Group",
                                  acronym="mars",
                                  parent=area.pk,
                                  ad=ad.pk,
                                  state=state.pk,
                                  chairs="aread@ietf.org, ad1@ietf.org",
                                  secretaries="aread@ietf.org, ad1@ietf.org, ad2@ietf.org",
                                  techadv="aread@ietf.org",
                                  delegates="ad2@ietf.org",
                                  list_email="mars@mail",
                                  list_subscribe="subscribe.mars",
                                  list_archive="archive.mars",
                                  urls="http://mars.mars (MARS site)"
                                  ))
        self.assertEqual(r.status_code, 302)

        group = Group.objects.get(acronym="mars")
        self.assertEqual(group.name, "Mars Not Special Interest Group")
        self.assertEqual(group.parent, area)
        self.assertEqual(group.ad_role().person, ad)
        for k in ("chair", "secr", "techadv"):
            self.assertTrue(group.role_set.filter(name=k, email__address="aread@ietf.org"))
        self.assertTrue(group.role_set.filter(name="delegate", email__address="ad2@ietf.org"))
        self.assertEqual(group.list_email, "mars@mail")
        self.assertEqual(group.list_subscribe, "subscribe.mars")
        self.assertEqual(group.list_archive, "archive.mars")
        self.assertEqual(group.groupurl_set.all()[0].url, "http://mars.mars")
        self.assertEqual(group.groupurl_set.all()[0].name, "MARS site")
        self.assertTrue(os.path.exists(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev))))
        self.assertEqual(len(outbox), 1)
        self.assertTrue('Personnel change' in outbox[0]['Subject'])
        for prefix in ['ad1','ad2','aread','marschairman','marsdelegate']:
            self.assertTrue(prefix+'@' in outbox[0]['To'])

    def test_initial_charter(self):
        make_test_data()
        group = Group.objects.get(acronym="mars")
        for url in [ urlreverse('ietf.group.edit.submit_initial_charter', kwargs={'acronym':group.acronym}),
                     urlreverse('ietf.group.edit.submit_initial_charter', kwargs={'acronym':group.acronym,'group_type':group.type_id}),
                   ]:
            login_testing_unauthorized(self, "secretary", url)
            r = self.client.get(url,follow=True)
            self.assertEqual(r.status_code,200) 
            self.assertTrue(r.redirect_chain[0][0].endswith(urlreverse('charter_submit',kwargs={'name':group.charter.name,'option':'initcharter'})))
            self.client.logout()
                    

    def test_conclude(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")

        url = urlreverse('ietf.group.edit.conclude', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=instructions]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(instructions="")) # No instructions
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

        # request conclusion
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(instructions="Test instructions"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue('iesg-secretary@' in outbox[-1]['To'])
        # the WG remains active until the Secretariat takes action
        group = Group.objects.get(acronym=group.acronym)
        self.assertEqual(group.state_id, "active")

class MilestoneTests(TestCase):
    def create_test_milestones(self):
        draft = make_test_data()

        group = Group.objects.get(acronym="mars")

        m1 = GroupMilestone.objects.create(id=1,
                                           group=group,
                                           desc="Test 1",
                                           due=datetime.date.today(),
                                           resolved="",
                                           state_id="active")
        m1.docs = [draft]

        m2 = GroupMilestone.objects.create(id=2,
                                           group=group,
                                           desc="Test 2",
                                           due=datetime.date.today(),
                                           resolved="",
                                           state_id="charter")
        m2.docs = [draft]

        return (m1, m2, group)

    def last_day_of_month(self, d):
        return datetime.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


    def test_milestone_sets(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(m1.desc in unicontent(r))
        self.assertTrue(m2.desc not in unicontent(r))

        url = urlreverse('group_edit_charter_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(m1.desc not in unicontent(r))
        self.assertTrue(m2.desc in unicontent(r))

    def test_add_milestone(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()
        docs = Document.objects.filter(type="draft").values_list("name", flat=True)

        due = self.last_day_of_month(datetime.date.today() + datetime.timedelta(days=365))

        # faulty post
        r = self.client.post(url, { 'prefix': "m-1",
                                    'm-1-id': "-1",
                                    'm-1-desc': "", # no description
                                    'm-1-due': due.strftime("%B %Y"),
                                    'm-1-resolved': "",
                                    'm-1-docs': ",".join(docs),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before)

        # add
        mailbox_before = len(outbox)
        r = self.client.post(url, { 'prefix': "m-1",
                                    'm-1-id': "-1",
                                    'm-1-desc': "Test 3",
                                    'm-1-due': due.strftime("%B %Y"),
                                    'm-1-resolved': "",
                                    'm-1-docs': ",".join(docs),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before + 1)
        self.assertEqual(group.groupevent_set.count(), events_before + 1)

        m = GroupMilestone.objects.get(desc="Test 3")
        self.assertEqual(m.state_id, "active")
        self.assertEqual(m.due, due)
        self.assertEqual(m.resolved, "")
        self.assertEqual(set(m.docs.values_list("name", flat=True)), set(docs))
        self.assertTrue("Added milestone" in m.milestonegroupevent_set.all()[0].desc)
        self.assertEqual(len(outbox),mailbox_before+2)
        self.assertFalse(any('Review Required' in x['Subject'] for x in outbox[-2:]))
        self.assertTrue('Milestones changed' in outbox[-2]['Subject'])
        self.assertTrue('mars-chairs@' in outbox[-2]['To'])
        self.assertTrue('aread@' in outbox[-2]['To'])
        self.assertTrue('Milestones changed' in outbox[-1]['Subject'])
        self.assertTrue('mars-wg@' in outbox[-1]['To'])

    def test_add_milestone_as_chair(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "marschairman", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()
        due = self.last_day_of_month(datetime.date.today() + datetime.timedelta(days=365))

        # add
        mailbox_before = len(outbox)
        r = self.client.post(url, { 'prefix': "m-1",
                                    'm-1-id': -1,
                                    'm-1-desc': "Test 3",
                                    'm-1-due': due.strftime("%B %Y"),
                                    'm-1-resolved': "",
                                    'm-1-docs': "",
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before + 1)

        m = GroupMilestone.objects.get(desc="Test 3")
        self.assertEqual(m.state_id, "review")
        self.assertEqual(group.groupevent_set.count(), events_before + 1)
        self.assertTrue("for review" in m.milestonegroupevent_set.all()[0].desc)
        self.assertEqual(len(outbox),mailbox_before+1)
        self.assertTrue('Review Required' in outbox[-1]['Subject'])
        self.assertFalse(group.list_email in outbox[-1]['To'])

    def test_accept_milestone(self):
        m1, m2, group = self.create_test_milestones()
        m1.state_id = "review"
        m1.save()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        events_before = group.groupevent_set.count()

        # add
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': m1.desc,
                                    'm1-due': m1.due.strftime("%B %Y"),
                                    'm1-resolved': m1.resolved,
                                    'm1-docs': ",".join(m1.docs.values_list("name", flat=True)),
                                    'm1-review': "accept",
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)

        m = GroupMilestone.objects.get(pk=m1.pk)
        self.assertEqual(m.state_id, "active")
        self.assertEqual(group.groupevent_set.count(), events_before + 1)
        self.assertTrue("to active from review" in m.milestonegroupevent_set.all()[0].desc)
        
    def test_delete_milestone(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()

        # delete
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': m1.desc,
                                    'm1-due': m1.due.strftime("%B %Y"),
                                    'm1-resolved': "",
                                    'm1-docs': ",".join(m1.docs.values_list("name", flat=True)),
                                    'm1-delete': "checked",
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before)
        self.assertEqual(group.groupevent_set.count(), events_before + 1)

        m = GroupMilestone.objects.get(pk=m1.pk)
        self.assertEqual(m.state_id, "deleted")
        self.assertTrue("Deleted milestone" in m.milestonegroupevent_set.all()[0].desc)

    def test_edit_milestone(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_edit_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()
        docs = Document.objects.filter(type="draft").values_list("name", flat=True)

        due = self.last_day_of_month(datetime.date.today() + datetime.timedelta(days=365))

        # faulty post
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': "", # no description
                                    'm1-due': due.strftime("%B %Y"),
                                    'm1-resolved': "",
                                    'm1-docs': ",".join(docs),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)
        m = GroupMilestone.objects.get(pk=m1.pk)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before)
        self.assertEqual(m.due, m1.due)

        # edit
        mailbox_before = len(outbox)
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': "Test 2 - changed",
                                    'm1-due': due.strftime("%B %Y"),
                                    'm1-resolved': "Done",
                                    'm1-resolved_checkbox': "checked",
                                    'm1-docs': ",".join(docs),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before)
        self.assertEqual(group.groupevent_set.count(), events_before + 1)

        m = GroupMilestone.objects.get(pk=m1.pk)
        self.assertEqual(m.state_id, "active")
        self.assertEqual(m.due, due)
        self.assertEqual(m.resolved, "Done")
        self.assertEqual(set(m.docs.values_list("name", flat=True)), set(docs))
        self.assertTrue("Changed milestone" in m.milestonegroupevent_set.all()[0].desc)
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Milestones changed" in outbox[-2]["Subject"])
        self.assertTrue(group.ad_role().email.address in str(outbox[-2]))
        self.assertTrue("Milestones changed" in outbox[-1]["Subject"])
        self.assertTrue(group.list_email in str(outbox[-1]))

    def test_reset_charter_milestones(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('group_reset_charter_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q('input[name=milestone]').val(), str(m1.pk))

        events_before = group.charter.docevent_set.count()

        # reset
        r = self.client.post(url, dict(milestone=[str(m1.pk)]))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(GroupMilestone.objects.get(pk=m1.pk).state_id, "active")
        self.assertEqual(GroupMilestone.objects.get(pk=m2.pk).state_id, "deleted")
        self.assertEqual(GroupMilestone.objects.filter(due=m1.due, desc=m1.desc, state="charter").count(), 1)

        self.assertEqual(group.charter.docevent_set.count(), events_before + 2) # 1 delete, 1 add

class CustomizeWorkflowTests(TestCase):
    def test_customize_workflow(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")

        url = urlreverse('ietf.group.edit.customize_workflow', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        state = State.objects.get(used=True, type="draft-stream-ietf", slug="wg-lc")
        self.assertTrue(state not in group.unused_states.all())

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form.set-state").find("input[name=state][value='%s']" % state.pk).parents("form").find("input[name=active][value='0']")), 1)

        # deactivate state
        r = self.client.post(url,
                             dict(action="setstateactive",
                                  state=state.pk,
                                  active="0"))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form.set-state").find("input[name=state][value='%s']" % state.pk).parents("form").find("input[name=active][value='1']")), 1)
        group = Group.objects.get(acronym=group.acronym)
        self.assertTrue(state in group.unused_states.all())

        # change next states
        state = State.objects.get(used=True, type="draft-stream-ietf", slug="wg-doc")
        next_states = State.objects.filter(used=True, type=b"draft-stream-ietf", slug__in=["parked", "dead", "wait-wgw", 'sub-pub']).values_list('pk', flat=True)
        r = self.client.post(url,
                             dict(action="setnextstates",
                                  state=state.pk,
                                  next_states=next_states))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form.set-next-states").find("input[name=state][value='%s']" % state.pk).parents('form').find("input[name=next_states][checked=checked]")), len(next_states))
        transitions = GroupStateTransitions.objects.filter(group=group, state=state)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(set(transitions[0].next_states.values_list("pk", flat=True)), set(next_states))

        # change them back to default
        next_states = state.next_states.values_list("pk", flat=True)
        r = self.client.post(url,
                             dict(action="setnextstates",
                                  state=state.pk,
                                  next_states=next_states))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(url)
        q = PyQuery(r.content)
        transitions = GroupStateTransitions.objects.filter(group=group, state=state)
        self.assertEqual(len(transitions), 0)

        # deactivate tag
        tag = DocTagName.objects.get(slug="w-expert")
        r = self.client.post(url,
                             dict(action="settagactive",
                                  tag=tag.pk,
                                  active="0"))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form').find('input[name=tag][value="%s"]' % tag.pk).parents("form").find("input[name=active]")), 1)
        group = Group.objects.get(acronym=group.acronym)
        self.assertTrue(tag in group.unused_tags.all())

class EmailAliasesTests(TestCase):

    def setUp(self):
        make_test_data()
        self.group_alias_file = NamedTemporaryFile(delete=False)
        self.group_alias_file.write("""# Generated by hand at 2015-02-12_16:30:52
virtual.ietf.org anything
mars-ads@ietf.org                                                xfilter-mars-ads
expand-mars-ads@virtual.ietf.org                                 aread@ietf.org
mars-chairs@ietf.org                                             xfilter-mars-chairs
expand-mars-chairs@virtual.ietf.org                              mars_chair@ietf.org
ames-ads@ietf.org                                                xfilter-mars-ads
expand-ames-ads@virtual.ietf.org                                 aread@ietf.org
ames-chairs@ietf.org                                             xfilter-mars-chairs
expand-ames-chairs@virtual.ietf.org                              mars_chair@ietf.org
""")
        self.group_alias_file.close()
        self.save_group_virtual_path = settings.GROUP_VIRTUAL_PATH
        settings.GROUP_VIRTUAL_PATH = self.group_alias_file.name

    def tearDown(self):
        settings.GROUP_VIRTUAL_PATH = self.save_group_virtual_path
        os.unlink(self.group_alias_file.name)

    def testAliases(self):
        url = urlreverse('old_group_email_aliases', kwargs=dict(acronym="mars"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

        for testdict in [dict(acronym="mars"),dict(acronym="mars",group_type="wg")]:
            url = urlreverse('old_group_email_aliases', kwargs=testdict)
            r = self.client.get(url,follow=True)
            self.assertTrue(all([x in unicontent(r) for x in ['mars-ads@','mars-chairs@']]))
            self.assertFalse(any([x in unicontent(r) for x in ['ames-ads@','ames-chairs@']]))

        url = urlreverse('ietf.group.info.email_aliases', kwargs=dict())
        login_testing_unauthorized(self, "plain", url)
        r = self.client.get(url)
        self.assertTrue(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['mars-ads@','mars-chairs@','ames-ads@','ames-chairs@']]))

        url = urlreverse('ietf.group.info.email_aliases', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue('mars-ads@' in unicontent(r))

        url = urlreverse('ietf.group.info.email_aliases', kwargs=dict(group_type="rg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertFalse('mars-ads@' in unicontent(r))

    def testExpansions(self):
        url = urlreverse('ietf.group.info.email', kwargs=dict(acronym="mars"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue('Email aliases' in unicontent(r))
        self.assertTrue('mars-ads@ietf.org' in unicontent(r))
        self.assertTrue('group_personnel_change' in unicontent(r))
 


class AjaxTests(TestCase):
    def test_group_menu_data(self):
        make_test_data()

        r = self.client.get(urlreverse("group_menu_data"))
        self.assertEqual(r.status_code, 200)

        parents = json.loads(r.content)

        area = Group.objects.get(type="area", acronym="farfut")
        self.assertTrue(str(area.id) in parents)

        mars_wg_data = None
        for g in parents[str(area.id)]:
            if g["acronym"] == "mars":
                mars_wg_data = g
                break
        self.assertTrue(mars_wg_data)

        mars_wg = Group.objects.get(acronym="mars")
        self.assertEqual(mars_wg_data["name"], mars_wg.name)

class MeetingInfoTests(TestCase):

    def setUp(self):
        self.group = GroupFactory.create(type_id='wg')
        today = datetime.date.today()
        SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=90))
        self.inprog = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1))
        SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today+datetime.timedelta(days=90))
        SessionFactory.create(meeting__type_id='interim',group=self.group,meeting__date=today+datetime.timedelta(days=45))


    def test_meeting_info(self):
        url = urlreverse('ietf.group.info.meetings',kwargs={'acronym':self.group.acronym})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) 
        q = PyQuery(response.content)
        self.assertTrue(q('#inprogressmeets'))
        self.assertTrue(q('#futuremeets'))
        self.assertTrue(q('#pastmeets'))

        self.group.session_set.filter(id=self.inprog.id).delete()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) 
        q = PyQuery(response.content)
        self.assertFalse(q('#inprogressmeets'))
        
