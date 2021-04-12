# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import shutil
import calendar
import datetime
import io
import bleach

from pyquery import PyQuery
from tempfile import NamedTemporaryFile

import debug                            # pyflakes:ignore

from django.conf import settings
from django.urls import reverse as urlreverse
from django.urls import NoReverseMatch
from django.utils import timezone
from django.contrib.auth.models import User

from django.utils.html import escape

from ietf.community.models import CommunityList
from ietf.community.utils import reset_name_contains_index_for_rule
from ietf.doc.factories import WgDraftFactory, CharterFactory, BallotDocEventFactory
from ietf.doc.models import Document, DocAlias, DocEvent, State
from ietf.doc.utils_charter import charter_name_for_group
from ietf.group.admin import GroupForm as AdminGroupForm
from ietf.group.factories import (GroupFactory, RoleFactory, GroupEventFactory, 
    DatedGroupMilestoneFactory, DatelessGroupMilestoneFactory)
from ietf.group.forms import GroupForm
from ietf.group.models import Group, GroupEvent, GroupMilestone, GroupStateTransitions, Role
from ietf.group.utils import save_group_in_history, setup_default_community_list_for_group
from ietf.meeting.factories import SessionFactory
from ietf.name.models import DocTagName, GroupStateName, GroupTypeName, ExtResourceName, RoleName
from ietf.person.models import Person, Email
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.review.factories import ReviewRequestFactory, ReviewAssignmentFactory
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent, reload_db_objects

def group_urlreverse_list(group, viewname):
    return [
        urlreverse(viewname, kwargs=dict(acronym=group.acronym)),
        urlreverse(viewname, kwargs=dict(acronym=group.acronym, group_type=group.type_id)),
    ]


def pklist(docs):
    return [ str(doc.pk) for doc in docs.all() ]

class GroupPagesTests(TestCase):
    def setUp(self):
        self.charter_dir = self.tempdir('charter')
        self.saved_charter_path = settings.CHARTER_PATH
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        settings.CHARTER_PATH = self.saved_charter_path
        shutil.rmtree(self.charter_dir)

    def test_active_groups(self):
        area = GroupFactory.create(type_id='area')
        group = GroupFactory.create(type_id='wg',parent=area)
        RoleFactory(group=group,name_id='ad',person=PersonFactory())

        url = urlreverse('ietf.group.views.active_groups', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, group.parent.name)
        self.assertContains(r, group.acronym)
        self.assertContains(r, group.name)
        self.assertContains(r, group.ad_role().person.plain_name())

        for t in ('rg','area','ag', 'rag', 'dir','review','team','program'):
            g = GroupFactory.create(type_id=t,state_id='active') 
            if t in ['dir','review']:
                g.parent = GroupFactory.create(type_id='area',state_id='active')
                g.save()
            url = urlreverse('ietf.group.views.active_groups', kwargs=dict(group_type=t))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, g.acronym)

        url = urlreverse('ietf.group.views.active_groups', kwargs=dict())
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Directorate")
        self.assertContains(r, "AG")

        for slug in GroupTypeName.objects.exclude(slug__in=['wg','rg','ag','rag','area','dir','review','team','program','adhoc','ise']).values_list('slug',flat=True):
            with self.assertRaises(NoReverseMatch):
                url=urlreverse('ietf.group.views.active_groups', kwargs=dict(group_type=slug))

    def test_group_home(self):
        draft = WgDraftFactory()
        group = draft.group
        # TODO - move this into GroupFactory
        setup_default_community_list_for_group(group)

        url_list = group_urlreverse_list(group, 'ietf.group.views.group_home')
        next_list = group_urlreverse_list(group, 'ietf.group.views.group_documents')
        for url, next in [ (url_list[i], next_list[i]) for i in range(len(url_list)) ]:
            r = self.client.get(url)
            self.assertRedirects(r, next)
            r = self.client.get(next)
            self.assertContains(r, group.acronym)
            self.assertContains(r, group.name)
            for word in ['Documents', 'Date', 'Status', 'IPR', 'AD', 'Shepherd']:
                self.assertContains(r, word)
            self.assertContains(r, draft.name)
            self.assertContains(r, draft.title)

    def test_wg_summaries(self):
        group = CharterFactory(group__type_id='wg',group__parent=GroupFactory(type_id='area')).group
        RoleFactory(group=group,name_id='chair',person=PersonFactory())
        RoleFactory(group=group,name_id='ad',person=PersonFactory())

        chair = Email.objects.filter(role__group=group, role__name="chair")[0]

        with io.open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")

        url = urlreverse('ietf.group.views.wg_summary_area', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, group.parent.name)
        self.assertContains(r, group.acronym)
        self.assertContains(r, group.name)
        self.assertContains(r, chair.address)

        url = urlreverse('ietf.group.views.wg_summary_acronym', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, group.acronym)
        self.assertContains(r, group.name)
        self.assertContains(r, chair.address)
        
        url = urlreverse('ietf.group.views.wg_charters', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, group.acronym)
        self.assertContains(r, group.name)
        self.assertContains(r, group.ad_role().person.plain_name())
        self.assertContains(r, chair.address)
        self.assertContains(r, "This is a charter.")

        url = urlreverse('ietf.group.views.wg_charters_by_acronym', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, group.acronym)
        self.assertContains(r, group.name)
        self.assertContains(r, group.ad_role().person.plain_name())
        self.assertContains(r, chair.address)
        self.assertContains(r, "This is a charter.")

    def test_chartering_groups(self):
        group = CharterFactory(group__type_id='wg',group__parent=GroupFactory(type_id='area'),states=[('charter','intrev')]).group

        url = urlreverse('ietf.group.views.chartering_groups')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertContains(r, "Charter new RG")
        self.assertContains(r, "Charter new WG")        

        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertNotContains(r, "Charter new RG")
        self.assertContains(r, "Charter new WG")

        self.client.login(username="irtf-chair", password="irtf-chair+password")
        r = self.client.get(url)
        self.assertContains(r, "Charter new RG")
        self.assertNotContains(r, "Charter new WG")

        self.client.logout()
        replaced_group = CharterFactory(group__state_id='replaced',group__type_id='wg',group__parent=GroupFactory(type_id='area'),states=[('charter','intrev')]).group
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % replaced_group.acronym)), 0)

    def test_concluded_groups(self):
        group = GroupFactory(state_id='conclude')

        url = urlreverse('ietf.group.views.concluded_groups')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)

    def test_bofs(self):
        group = GroupFactory(state_id='bof')

        url = urlreverse('ietf.group.views.bofs', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content a:contains("%s")' % group.acronym)), 1)
        
    def test_group_documents(self):
        group = GroupFactory()
        setup_default_community_list_for_group(group)
        draft = WgDraftFactory(group=group)
        draft.action_holders.set([PersonFactory()])
        draft2 = WgDraftFactory(group=group)
        draft3 = WgDraftFactory(group=group)
        draft3.set_state(State.objects.get(type='draft-iesg', slug='pub-req'))
        draft3.action_holders.set(PersonFactory.create_batch(2))
        old_dah = draft3.documentactionholder_set.first()
        old_dah.time_added -= datetime.timedelta(days=173)  # make an "old" action holder
        old_dah.save()

        clist = CommunityList.objects.get(group=group)
        related_docs_rule = clist.searchrule_set.get(rule_type='name_contains')
        reset_name_contains_index_for_rule(related_docs_rule)

        for url in group_urlreverse_list(group, 'ietf.group.views.group_documents'):
            with self.settings(DOC_ACTION_HOLDER_MAX_AGE_DAYS=20):
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, draft.name)
            self.assertContains(r, group.name)
            self.assertContains(r, group.acronym)
            self.assertNotContains(r, draft.action_holders.first().plain_name())
            self.assertContains(r, draft2.name)
            self.assertContains(r, draft3.name)
            for ah in draft3.action_holders.all():
                self.assertContains(r, ah.plain_name())
            self.assertContains(r, 'for 173 days', count=1)  # the old_dah should be tagged

        # Make sure that a logged in user is presented with an opportunity to add results to their community list
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue(any([draft2.name in x.attrib['href'] for x in q('table td a.track-untrack-doc')]))

        # test the txt version too while we're at it
        for url in group_urlreverse_list(group, 'ietf.group.views.group_documents_txt'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, draft.name)
            self.assertContains(r, draft2.name)

    def test_group_charter(self):
        group = CharterFactory().group
        draft = WgDraftFactory(group=group)

        with io.open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")

        milestone = GroupMilestone.objects.create(
            group=group,
            state_id="active",
            desc="Get Work Done",
            due=datetime.date.today() + datetime.timedelta(days=100))
        milestone.docs.add(draft)

        for url in [group.about_url(),] + group_urlreverse_list(group, 'ietf.group.views.group_about'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, group.name)
            self.assertContains(r, group.acronym)
            self.assertContains(r, "This is a charter.")
            self.assertContains(r, milestone.desc)
            self.assertContains(r, milestone.docs.all()[0].name)

    def test_group_about(self):

        RoleFactory(group=Group.objects.get(acronym='iab'),name_id='member',person=PersonFactory(user__username='iab-member'))

        interesting_users = [ 'plain','iana','iab-chair','irtf-chair', 'marschairman', 'teamchairman','ad', 'iab-member', 'secretary', ]

        can_edit = {
            'wg'   : ['secretary','ad'],
            'rg'   : ['secretary','irtf-chair'],
            'ag'   : ['secretary', 'ad' ],
            'rag'  : ['secretary', 'irtf-chair'],
            'team' : ['secretary',], # The code currently doesn't let ads edit teams or directorates. Maybe it should.
            'dir'  : ['secretary',],
            'review'  : ['secretary',],
            'program' : ['secretary', 'iab-member'],
        }

        def setup_role(group, role_id):
            p = PersonFactory(user__username="%s_%s"%(group.acronym,role_id))
            group.role_set.create(name_id=role_id,person=p,email=p.email())
            can_edit[group.type_id].append(p.user.username)
            interesting_users.append(p.user.username)

        test_groups = []

        for t in ['wg','rg','ag','rag','team']:
            g = GroupFactory(type_id=t)
            setup_role(g,'chair')
            test_groups.append(g)

        for t in ['dir','review',]:
            g = GroupFactory(type_id=t)
            setup_role(g,'secr')
            test_groups.append(g)

        g = GroupFactory(type_id='program')
        setup_role(g, 'lead')
        test_groups.append(g)

        def verify_cannot_edit_group(url, group, username):
            self.client.logout()
            self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertTrue(r.status_code in (302,403),"%s should not be able to edit %s of type %s"%(username,group.acronym,group.type_id))

        def verify_can_edit_group(url, group, username):
            self.client.logout()
            self.client.login(username=username, password=username+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, "%s should be able to edit %s of type %s"%(username,group.acronym,group.type_id))

        for group in test_groups:

            for url in [group.about_url(),] + group_urlreverse_list(group, 'ietf.group.views.group_about'):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, group.name)
                self.assertContains(r, group.acronym)
                self.assertContains(r, group.description)
    
            for url in group_urlreverse_list(group, 'ietf.group.views.edit'):
    
                for username in can_edit[group.type_id]:
                    verify_can_edit_group(url, group, username)
    
                for username in list(set(interesting_users)-set(can_edit[group.type_id])):
                    verify_cannot_edit_group(url, group, username)

    def test_group_about_personnel(self):
        """Correct personnel should appear on the group About page"""
        group = GroupFactory()
        for role_name in group.features.default_used_roles:
            RoleFactory.create_batch(2, group=group, name=RoleName.objects.get(slug=role_name))

        for url in [group.about_url(),] + group_urlreverse_list(group, 'ietf.group.views.group_about'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            
            for role in group.role_set.all():
                self.assertContains(r, role.person.plain_name())

    def test_materials(self):
        group = GroupFactory(type_id="team", acronym="testteam", name="Test Team", state_id="active")

        doc = Document.objects.create(
            name="slides-testteam-test-slides",
            rev="00",
            title="Test Slides",
            group=group,
            type_id="slides",
        )
        doc.set_state(State.objects.get(type="slides", slug="active"))
        DocAlias.objects.create(name=doc.name).docs.add(doc)

        for url in group_urlreverse_list(group, 'ietf.group.views.materials'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, doc.title)
            self.assertContains(r, doc.name)

        url =  urlreverse("ietf.group.views.materials", kwargs={ 'acronym': group.acronym })

        # try deleting the document and check it's gone
        doc.set_state(State.objects.get(type="slides", slug="deleted"))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, doc.title)

    def test_history(self):
        group = GroupFactory()

        e = GroupEvent.objects.create(
            group=group,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        for url in group_urlreverse_list(group, 'ietf.group.views.history'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, e.desc)

    def test_feed(self):
        group = CharterFactory().group

        ge = GroupEvent.objects.create(
            group=group,
            desc="Something happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        de = DocEvent.objects.create(
            doc=group.charter,
            rev=group.charter.rev,
            desc="Something else happened.",
            type="added_comment",
            by=Person.objects.get(name="(System)"))

        r = self.client.get("/feed/group-changes/%s/" % group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ge.desc)
        self.assertContains(r, de.desc)


    def test_chair_photos(self):
        RoleFactory(name_id='chair')
        url = urlreverse("ietf.group.views.chair_photos", kwargs={'group_type':'wg'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        chairs = Role.objects.filter(group__type='wg', group__state='active', name_id='chair')
        self.assertEqual(len(q('div.photo-thumbnail img')), chairs.count())

    def test_wg_photos(self):
        GroupFactory(acronym='mars')
        RoleFactory(name_id='chair')
        RoleFactory(name_id='secr')
        url = urlreverse("ietf.group.views.group_photos", kwargs={'group_type':'wg', 'acronym':'mars'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        roles = Role.objects.filter(group__acronym='mars')
        self.assertEqual(len(q('div.photo-thumbnail img')), roles.count())

    def test_group_photos(self):
        url = urlreverse("ietf.group.views.group_photos", kwargs={'acronym':'iab'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        roles = Role.objects.filter(group__acronym='iab')
        self.assertEqual(len(q('div.photo-thumbnail img')), roles.count())

    def test_nonactive_group_badges(self):
        concluded_group = GroupFactory(state_id='conclude')
        url = urlreverse("ietf.group.views.history",kwargs={'acronym':concluded_group.acronym})
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(q('.label-warning').text(),"Concluded WG")
        replaced_group = GroupFactory(state_id='replaced')
        url = urlreverse("ietf.group.views.history",kwargs={'acronym':replaced_group.acronym})
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(q('.label-warning').text(),"Replaced WG")


class GroupEditTests(TestCase):
    def setUp(self):
        self.charter_dir = self.tempdir('charter')
        self.saved_charter_path = settings.CHARTER_PATH
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        settings.CHARTER_PATH = self.saved_charter_path
        shutil.rmtree(self.charter_dir)

    def test_create(self):

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type="wg", action="charter"))
        login_testing_unauthorized(self, "secretary", url)

        num_wgs = len(Group.objects.filter(type="wg"))

        bof_state = GroupStateName.objects.get(slug="bof")

        area = Group.objects.filter(type="area").first()

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
        self.assertTrue(len(q('form .has-error')) > 0)

        # acronym contains hyphen
        r = self.client.post(url, dict(acronym="test-wg", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('form .has-error')) > 0)

        # acronym too short
        r = self.client.post(url, dict(acronym="t", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('form .has-error')) > 0)

        # acronym doesn't start with an alpha character
        r = self.client.post(url, dict(acronym="1startwithalpha", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('form .has-error')) > 0)

        # no parent group given
        r = self.client.post(url, dict(acronym="testwg", name="Testing WG", state=bof_state.pk))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(q('form .has-error')) > 0)

        # Ok creation
        r = self.client.post(url, dict(acronym="testwg", name="Testing WG", state=bof_state.pk, parent=area.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(Group.objects.filter(type="wg")), num_wgs + 1)
        group = Group.objects.get(acronym="testwg")
        self.assertEqual(group.name, "Testing WG")
        self.assertEqual(charter_name_for_group(group), "charter-ietf-testwg")

    def test_create_rg(self):

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type="rg", action="charter"))
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
        self.assertEqual(charter_name_for_group(group), "charter-irtf-testrg")

    def test_create_based_on_existing_bof(self):

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type="wg", action="charter"))
        login_testing_unauthorized(self, "secretary", url)

        group = GroupFactory(acronym="mars",parent=GroupFactory(type_id='area'))

        # try hijacking area - faulty
        r = self.client.post(url, dict(name="Test", acronym=group.parent.acronym))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

        # try elevating BoF to WG
        group.state_id = "bof"
        group.save()

        r = self.client.post(url, dict(name="Test", acronym=group.acronym))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .has-error')) > 0)

        self.assertEqual(Group.objects.get(acronym=group.acronym).state_id, "bof")

#         # confirm elevation
#         state = GroupStateName.objects.get(slug="proposed")
#         r = self.client.post(url, dict(name="Test", acronym=group.acronym, confirm_acronym="1", state=state.pk))
#         self.assertEqual(r.status_code, 302)
#         self.assertEqual(Group.objects.get(acronym=group.acronym).state_id, "proposed")
#         self.assertEqual(Group.objects.get(acronym=group.acronym).name, "Test")

    def test_edit_info(self):
        group = GroupFactory(acronym='mars',parent=GroupFactory(type_id='area'))
        CharterFactory(group=group)
        RoleFactory(group=group,name_id='chair',person__user__email='marschairman@example.org')
        RoleFactory(group=group,name_id='delegate',person__user__email='marsdelegate@example.org')

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type=group.type_id, acronym=group.acronym, action="edit"))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=parent]')), 1)
        self.assertEqual(len(q('form input[name=acronym]')), 1)
        for role_slug in group.used_roles or group.features.default_used_roles:
            self.assertEqual(len(q('form input[name=%s_roles]'%role_slug)),1)

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
        with io.open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
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
                                  chair_roles="aread@example.org, ad1@example.org",
                                  secr_roles="aread@example.org, ad1@example.org, ad2@example.org",
                                  liaison_contact_roles="ad1@example.org",
                                  liaison_cc_contact_roles="aread@example.org, ad2@example.org",
                                  techadv_roles="aread@example.org",
                                  delegate_roles="ad2@example.org",
                                  list_email="mars@mail",
                                  list_subscribe="subscribe.mars",
                                  list_archive="archive.mars",
                                  ))
        self.assertEqual(r.status_code, 302)

        group = Group.objects.get(acronym="mars")
        self.assertEqual(group.name, "Mars Not Special Interest Group")
        self.assertEqual(group.parent, area)
        self.assertEqual(group.ad_role().person, ad)
        for k in ("chair", "secr", "techadv", "liaison_cc_contact"):
            self.assertTrue(group.role_set.filter(name=k, email__address="aread@example.org"))
        self.assertTrue(group.role_set.filter(name='liaison_contact', email__address='ad1@example.org'))
        self.assertFalse(group.role_set.filter(name='liaison_contact', email__address='aread@example.org'))
        self.assertFalse(group.role_set.filter(name='liaison_contact', email__address='ad2@example.org'))
        self.assertFalse(group.role_set.filter(name='liaison_cc_contact', email__address='ad1@example.org'))
        self.assertTrue(group.role_set.filter(name='liaison_cc_contact', email__address='ad2@example.org'))
        self.assertTrue(group.role_set.filter(name="delegate", email__address="ad2@example.org"))
        self.assertEqual(group.list_email, "mars@mail")
        self.assertEqual(group.list_subscribe, "subscribe.mars")
        self.assertEqual(group.list_archive, "archive.mars")

        self.assertTrue(os.path.exists(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev))))
        self.assertEqual(len(outbox), 2)
        self.assertTrue('Personnel change' in outbox[0]['Subject'])
        for prefix in ['ad1','ad2','aread','marschairman','marsdelegate']:
            self.assertTrue(prefix+'@' in outbox[0]['To'])
        self.assertTrue(get_payload_text(outbox[0]).startswith('Sec Retary'))

    def test_edit_extresources(self):
        group = GroupFactory(acronym='mars',parent=GroupFactory(type_id='area'))
        CharterFactory(group=group)
        ExtResourceName.objects.create(slug='keymaster', name='Keymaster', type_id='email')

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type=group.type_id, acronym=group.acronym, action="edit", field="resources"))
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_resources]')),1)

        badlines = (
            'github_repo https://github3.com/some/repo',
            'github_notify  badaddr',
            'website /not/a/good/url',
            'notavalidtag blahblahblah',
            'github_repo',
        )

        for line in badlines:
            r = self.client.post(url, dict(resources=line, submit="1"))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('.alert-danger'))

        goodlines = """
            github_repo https://github.com/some/repo Some display text
            github_username githubuser
            webpage http://example.com/http/is/fine
            jabber_room xmpp:mars@jabber.example.com
            keymaster keymaster@example.org Group Rooter
        """

        r = self.client.post(url, dict(resources=goodlines, submit="1"))
        self.assertEqual(r.status_code,302)
        group = Group.objects.get(acronym=group.acronym)
        self.assertEqual(group.latest_event(GroupEvent,type="info_changed").desc[:20], 'Resources changed to')
        self.assertIn('github_username githubuser', group.latest_event(GroupEvent,type="info_changed").desc)
        self.assertEqual(group.groupextresource_set.count(), 5)
        self.assertEqual(group.groupextresource_set.get(name__slug='github_repo').display_name, 'Some display text')
        self.assertIn(group.groupextresource_set.first().name.slug, str(group.groupextresource_set.first()))

        # exercise format_resources
        r = self.client.get(url)
        self.assertIn('Group Rooter', unicontent(r))


    def test_edit_field(self):
        def _test_field(group, field_name, field_content, prohibited_form_names):
            url = urlreverse('ietf.group.views.edit', 
                             kwargs=dict(
                                 acronym=group.acronym, 
                                 action="edit", 
                                 field=field_name
                             ))
            login_testing_unauthorized(self, "secretary", url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

            q = PyQuery(r.content)
            self.assertEqual(len(q('div#content > form input[name=%s]' % field_name)), 1)
            for prohibited_name in prohibited_form_names:
                self.assertEqual(len(q('div#content > form input[name=%s]' % prohibited_name)), 0)

            # edit info
            r = self.client.post(url, {field_name: field_content})
            self.assertEqual(r.status_code, 302)

            #
            group = Group.objects.get(acronym=group.acronym)
            if field_name.endswith('_roles'):
                role_name = field_name[:-len('_roles')]
                self.assertSetEqual(
                    {fc.strip() for fc in field_content.split(',')},
                    set(group.role_set.filter(name=role_name).values_list('email', flat=True))
                )
            else:
                self.assertEqual(getattr(group, field_name), field_content)
            self.client.logout()

        group = GroupFactory(acronym="mars")
        EmailFactory(address='user@example.com')
        EmailFactory(address='other_user@example.com')

        # Test various fields
        _test_field(group, 'name', 'Mars Not Special Interest Group', ['acronym'])
        _test_field(group, 'list_email', 'mars@mail', ['name'])
        _test_field(group, 'liaison_contact_roles', 'user@example.com, other_user@example.com', ['list_email'])
        _test_field(group, 'liaison_cc_contact_roles', 'user@example.com, other_user@example.com', ['liaison_contact'])

    def test_edit_reviewers(self):
        group=GroupFactory(type_id='review',parent=GroupFactory(type_id='area'))
        review_req = ReviewRequestFactory(team=group)
        ad_email = Email.objects.get(address='ad2@example.org')

        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type=group.type_id, acronym=group.acronym, action="edit"))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=reviewer_roles]')), 1)

        # set reviewers
        empty_outbox()
        post_data = dict(
            name=group.name,
            acronym=group.acronym,
            parent=group.parent_id,
            ad=Person.objects.get(name="Areað Irector").pk,
            state=group.state_id,
            list_email=group.list_email,
            list_subscribe=group.list_subscribe,
            list_archive=group.list_archive,
            urls=""
        )
        r = self.client.post(url, dict(post_data, reviewer_roles=ad_email.address))
        self.assertEqual(r.status_code, 302)

        group = reload_db_objects(group)
        self.assertEqual(list(group.role_set.filter(name="reviewer").values_list("email", flat=True)), [ad_email.address])
        self.assertTrue('Personnel change' in outbox[0]['Subject'])
        
        # Assign a review to the reviewer, then remove the reviewer from the group
        # As the request deadline has not passed, the assignment should be set to rejected
        review_assignment = ReviewAssignmentFactory(review_request=review_req, state_id='assigned', reviewer=ad_email)
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        group = reload_db_objects(group)
        self.assertFalse(group.role_set.filter(name="reviewer"))
        review_assignment = reload_db_objects(review_assignment)
        self.assertEqual(review_assignment.state_id, 'rejected')

        # Repeat after adding reviewer again, but now beyond request deadline
        r = self.client.post(url, dict(post_data, reviewer_roles=ad_email.address))
        self.assertEqual(r.status_code, 302)
        review_assignment.state_id = 'accepted'
        review_assignment.save()
        review_req.deadline = datetime.date.today() - datetime.timedelta(days=1)
        review_req.save()
        
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        review_assignment = reload_db_objects(review_assignment)
        self.assertEqual(review_assignment.state_id, 'no-response')

    def test_conclude(self):
        group = GroupFactory(acronym="mars")

        url = urlreverse('ietf.group.views.conclude', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
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

    def test_replace(self):
        group = GroupFactory(state_id='bof')
        charter = CharterFactory(group=group, states=[('charter','intrev')])
        BallotDocEventFactory(doc=charter, ballot_type__doc_type_id='draft', ballot_type__slug='r-extrev')
        url = urlreverse('ietf.group.views.edit', kwargs=dict(group_type=group.type_id, acronym=group.acronym, action="edit", field="state"))
        self.client.login(username='secretary',password='secretary+password')
        self.client.post(url, dict(state='replaced'))
        group = Group.objects.get(pk=group.pk)       
        self.assertEqual(group.state_id, 'replaced')
        self.assertEqual(group.charter.get_state_slug('charter'), 'replaced')
        self.assertEqual(group.charter.active_ballot(), None)


    def test_add_comment(self):
        group = GroupFactory(acronym="mars",parent=GroupFactory(type_id='area'))
        RoleFactory(group=group,person=Person.objects.get(user__username='ad'),name_id='ad')
        RoleFactory(group=group,person__user__username='marschairman',name_id='chair')
        RoleFactory(group=group,person__user__username='marssecretary',name_id='secr')
        RoleFactory(group=group,person__user__username='marsdelegate',name_id='delegate')
        url = urlreverse('ietf.group.views.add_comment', kwargs=dict(acronym=group.acronym))
        empty_outbox()
        for username in ['secretary','ad','marschairman','marssecretary','marsdelegate']:
            login_testing_unauthorized(self, username, url)
            # get
            r = self.client.get(url)
            self.assertContains(r, "Add comment")
            self.assertContains(r, group.acronym)
            q = PyQuery(r.content)
            self.assertEqual(len(q('form textarea[name=comment]')), 1)
            # post
            r = self.client.post(url, dict(comment="Test comment %s"%username))
            self.assertEqual(r.status_code, 302)
            person = Person.objects.get(user__username=username)
            self.assertTrue(GroupEvent.objects.filter(group=group,by=person,type='added_comment',desc='Test comment %s'%username).exists())
            self.client.logout()
        self.client.login(username='ameschairman',password='ameschairman+password')
        r=self.client.get(url)
        self.assertEqual(r.status_code,403)
        self.assertEqual(len(outbox),5)

class MilestoneTests(TestCase):
    def create_test_milestones(self):
        group = GroupFactory(acronym='mars',parent=GroupFactory(type_id='area'),list_email='mars-wg@ietf.org')
        CharterFactory(group=group)
        RoleFactory(group=group,name_id='ad',person=Person.objects.get(user__username='ad'))
        RoleFactory(group=group,name_id='chair',person=PersonFactory(user__username='marschairman'))
        draft = WgDraftFactory(group=group)

        m1 = GroupMilestone.objects.create(id=1,
                                           group=group,
                                           desc="Test 1",
                                           due=datetime.date.today(),
                                           resolved="",
                                           state_id="active")
        m1.docs.set([draft])

        m2 = GroupMilestone.objects.create(id=2,
                                           group=group,
                                           desc="Test 2",
                                           due=datetime.date.today(),
                                           resolved="",
                                           state_id="charter")
        m2.docs.set([draft])

        return (m1, m2, group)

    def last_day_of_month(self, d):
        return datetime.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


    def test_milestone_sets(self):
        m1, m2, group = self.create_test_milestones()

        for url in group_urlreverse_list(group, 'ietf.group.milestones.edit_milestones;current'):
            login_testing_unauthorized(self, "secretary", url)

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, m1.desc)
            self.assertNotContains(r, m2.desc)
            self.client.logout()

        login_testing_unauthorized(self, "secretary", url)

        for url in group_urlreverse_list(group, 'ietf.group.milestones.edit_milestones;charter'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, m1.desc)
            self.assertContains(r, m2.desc)

    def test_add_milestone(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()
        doc_pks = pklist(Document.objects.filter(type="draft"))

        due = self.last_day_of_month(datetime.date.today() + datetime.timedelta(days=365))

        # faulty post
        r = self.client.post(url, { 'prefix': "m-1",
                                    'm-1-id': "-1",
                                    'm-1-desc': "", # no description
                                    'm-1-due': due.strftime("%B %Y"),
                                    'm-1-resolved': "",
                                    'm-1-docs': ",".join(doc_pks),
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
                                    'm-1-docs': ",".join(doc_pks),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before + 1)
        self.assertEqual(group.groupevent_set.count(), events_before + 1)

        m = GroupMilestone.objects.get(desc="Test 3")
        self.assertEqual(m.state_id, "active")
        self.assertEqual(m.due, due)
        self.assertEqual(m.resolved, "")
        self.assertEqual(set(pklist(m.docs)), set(doc_pks))
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

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "marschairman", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        milestones_before = GroupMilestone.objects.filter(group=group).count()
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
        m = GroupMilestone.objects.filter(group=group)
        self.assertEqual(m.count(), milestones_before + 1)

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

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
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
                                    'm1-docs': ",".join(pklist(m1.docs)),
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

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()

        # delete
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': m1.desc,
                                    'm1-due': m1.due.strftime("%B %Y"),
                                    'm1-resolved': "",
                                    'm1-docs': ",".join(pklist(m1.docs)),
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

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        milestones_before = GroupMilestone.objects.count()
        events_before = group.groupevent_set.count()
        doc_pks = pklist(Document.objects.filter(type="draft"))

        due = self.last_day_of_month(datetime.date.today() + datetime.timedelta(days=365))

        # faulty post
        r = self.client.post(url, { 'prefix': "m1",
                                    'm1-id': m1.id,
                                    'm1-desc': "", # no description
                                    'm1-due': due.strftime("%B %Y"),
                                    'm1-resolved': "",
                                    'm1-docs': ",".join(doc_pks),
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
                                    'm1-docs': ",".join(doc_pks),
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GroupMilestone.objects.count(), milestones_before)
        self.assertEqual(group.groupevent_set.count(), events_before + 1)

        m = GroupMilestone.objects.get(pk=m1.pk)
        self.assertEqual(m.state_id, "active")
        self.assertEqual(m.due, due)
        self.assertEqual(m.resolved, "Done")
        self.assertEqual(set(pklist(m.docs)), set(doc_pks))
        self.assertTrue("Changed milestone" in m.milestonegroupevent_set.all()[0].desc)
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue("Milestones changed" in outbox[-2]["Subject"])
        self.assertTrue(group.ad_role().email.address in str(outbox[-2]))
        self.assertTrue("Milestones changed" in outbox[-1]["Subject"])
        self.assertTrue(group.list_email in str(outbox[-1]))

    def test_reset_charter_milestones(self):
        m1, m2, group = self.create_test_milestones()

        url = urlreverse('ietf.group.milestones.reset_charter_milestones', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
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

class DatelessMilestoneTests(TestCase):
    def test_switch_to_dateless(self):
        ad_role = RoleFactory(group__type_id='area',name_id='ad')
        ms = DatedGroupMilestoneFactory(group__parent=ad_role.group)
        ad = ad_role.person
        chair = RoleFactory(group=ms.group,name_id='chair').person

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(acronym=ms.group.acronym))
        login_testing_unauthorized(self, chair.user.username, url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#switch-date-use-form')),0)

        r = self.client.post(url, dict(action="switch"))
        self.assertEqual(r.status_code, 403)

        self.client.logout()
        self.client.login(username=ad.user.username, password='%s+password' % ad.user.username)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#switch-date-use-form')),1)
        self.assertEqual(len(q('#uses_milestone_dates')),1)

        r = self.client.post(url, dict(action="switch"))
        self.assertEqual(r.status_code, 200)
        ms = GroupMilestone.objects.get(id=ms.id)
        self.assertFalse(ms.group.uses_milestone_dates)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#uses_milestone_dates')),0)

    def test_switch_to_dated(self):
        ad_role = RoleFactory(group__type_id='area',name_id='ad')
        ms = DatelessGroupMilestoneFactory(group__parent=ad_role.group)
        ad = ad_role.person

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(acronym=ms.group.acronym))
        login_testing_unauthorized(self, ad.user.username, url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#uses_milestone_dates')),0)

        r = self.client.post(url, dict(action="switch"))
        self.assertEqual(r.status_code, 200)
        ms = GroupMilestone.objects.get(id=ms.id)
        self.assertTrue(ms.group.uses_milestone_dates)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#uses_milestone_dates')),1)

    def test_add_first_milestone(self):
        role = RoleFactory(name_id='chair',group__uses_milestone_dates=False)
        group = role.group
        chair = role.person

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, chair.user.username, url)

        r = self.client.post(url, { 'prefix': "m-1",
                                    'm-1-id': -1,
                                    'm-1-desc': "Test 3",
                                    'm-1-order': 1,
                                    'm-1-resolved': "",
                                    'm-1-docs': "",
                                    'action': "save",
                                    })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(group.groupmilestone_set.count(),1)

    def test_can_switch_date_types_for_initial_charter(self):
        ad_role = RoleFactory(group__type_id='area',name_id='ad')
        ms = DatedGroupMilestoneFactory(group__parent=ad_role.group)
        ad = ad_role.person   
        ms.group.charter = CharterFactory(group=ms.group)
        
        url = urlreverse('ietf.group.milestones.edit_milestones;charter', kwargs=dict(acronym=ms.group.acronym))
        login_testing_unauthorized(self, ad.user.username, url)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q('#switch-date-use-form button').attr('style'), 'display:none;')     

        ms.group.charter.rev='00-00'
        ms.group.charter.save()
        
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(q('#switch-date-use-form button').attr('style'), None)          

    def test_edit_and_reorder_milestone(self):
        role = RoleFactory(name_id='chair',group__uses_milestone_dates=False)
        group = role.group

        DatelessGroupMilestoneFactory.create_batch(3,group=group)

        url = urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        post_data = dict()
        prefixes = []
        for ms in group.groupmilestone_set.order_by('order'):
            prefix = 'm%d' % ms.id
            prefixes.append(prefix)
            post_data['%s-id' % prefix] = ms.id
            post_data['%s-desc' % prefix] = ms.desc
            post_data['%s-order' % prefix] = ms.order
            post_data['%s-docs' % prefix] = ""

        post_data['prefix'] = prefixes
        post_data['action'] = 'review'

        # Change the second milestone's description
        post_data['%s-desc' % prefixes[1]] = '2s09dhfbn23tn'
        # Switch the order of the first and second milestone
        post_data['%s-order' % prefixes[0]] = 2
        post_data['%s-order' % prefixes[1]] = 1

        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('.label:contains("Changed")')), 2)

        post_data['action'] = 'save'
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)

        milestones = group.groupmilestone_set.order_by('order')
        self.assertEqual(milestones[0].desc,'2s09dhfbn23tn')

class CustomizeWorkflowTests(TestCase):
    def test_customize_workflow(self):

        group = GroupFactory()

        url = urlreverse('ietf.group.views.customize_workflow', kwargs=dict(group_type=group.type_id, acronym=group.acronym))
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
        PersonFactory(user__username='plain')
        GroupFactory(acronym='mars',parent=GroupFactory(type_id='area'))
        GroupFactory(acronym='ames',parent=GroupFactory(type_id='area'))
        self.group_alias_file = NamedTemporaryFile(delete=False)
        self.group_alias_file.write(b"""# Generated by hand at 2015-02-12_16:30:52
virtual.ietf.org anything
mars-ads@ietf.org                                                xfilter-mars-ads
expand-mars-ads@virtual.ietf.org                                 aread@example.org
mars-chairs@ietf.org                                             xfilter-mars-chairs
expand-mars-chairs@virtual.ietf.org                              mars_chair@ietf.org
ames-ads@ietf.org                                                xfilter-mars-ads
expand-ames-ads@virtual.ietf.org                                 aread@example.org
ames-chairs@ietf.org                                             xfilter-mars-chairs
expand-ames-chairs@virtual.ietf.org                              mars_chair@ietf.org
""")
        self.group_alias_file.close()
        self.saved_group_virtual_path = settings.GROUP_VIRTUAL_PATH
        settings.GROUP_VIRTUAL_PATH = self.group_alias_file.name

    def tearDown(self):
        settings.GROUP_VIRTUAL_PATH = self.saved_group_virtual_path
        os.unlink(self.group_alias_file.name)

    def testAliases(self):
        url = urlreverse('ietf.group.urls_info_details.redirect.email', kwargs=dict(acronym="mars"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

        for testdict in [dict(acronym="mars"),dict(acronym="mars",group_type="wg")]:
            url = urlreverse('ietf.group.urls_info_details.redirect.email', kwargs=testdict)
            r = self.client.get(url,follow=True)
            self.assertTrue(all([x in unicontent(r) for x in ['mars-ads@','mars-chairs@']]))
            self.assertFalse(any([x in unicontent(r) for x in ['ames-ads@','ames-chairs@']]))

        url = urlreverse('ietf.group.views.email_aliases', kwargs=dict())
        login_testing_unauthorized(self, "plain", url)
        r = self.client.get(url)
        self.assertTrue(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['mars-ads@','mars-chairs@','ames-ads@','ames-chairs@']]))

        url = urlreverse('ietf.group.views.email_aliases', kwargs=dict(group_type="wg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertContains(r, 'mars-ads@')

        url = urlreverse('ietf.group.views.email_aliases', kwargs=dict(group_type="rg"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotContains(r, 'mars-ads@')

    def testExpansions(self):
        url = urlreverse('ietf.group.views.email', kwargs=dict(acronym="mars"))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertContains(r, 'Email aliases')
        self.assertContains(r, 'mars-ads@ietf.org')
        self.assertContains(r, 'group_personnel_change')
 


class AjaxTests(TestCase):
    def test_group_menu_data(self):

        GroupFactory(acronym='mars',parent=Group.objects.get(acronym='farfut'))

        r = self.client.get(urlreverse('ietf.group.views.group_menu_data'))
        self.assertEqual(r.status_code, 200)

        parents = r.json()

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
        SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=14))
        self.inprog = SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today-datetime.timedelta(days=1))
        SessionFactory.create(meeting__type_id='ietf',group=self.group,meeting__date=today+datetime.timedelta(days=90))
        SessionFactory.create(meeting__type_id='interim',group=self.group,meeting__date=today+datetime.timedelta(days=45))


    def test_meeting_info(self):
        for url in group_urlreverse_list(self.group, 'ietf.group.views.meetings'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200) 
            q = PyQuery(response.content)
            self.assertTrue(q('#inprogressmeets'))
            self.assertTrue(q('#futuremeets'))
            self.assertTrue(q('#pastmeets'))
            # This should be improved to make sure each session shows up in the right section above
            for session in self.group.session_set.all():
                self.assertIn(session.meeting.number,unicontent(response))

        self.group.session_set.filter(id=self.inprog.id).delete()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) 
        q = PyQuery(response.content)
        self.assertFalse(q('#inprogressmeets'))
        

class StatusUpdateTests(TestCase):

    def test_unsupported_group_types(self):

        def ensure_updates_dont_show(group, user):
            url = urlreverse('ietf.group.views.group_about',kwargs={'acronym':group.acronym})
            if user:
                self.client.login(username=user.username,password='%s+password'%user.username)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertFalse(q('tr#status_update') )
            self.client.logout()

        def ensure_cant_edit(group,user):
            url = urlreverse('ietf.group.views.group_about_status_edit',kwargs={'acronym':group.acronym})
            if user:
                self.client.login(username=user.username,password='%s+password'%user.username)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.client.logout()

        for type_id in GroupTypeName.objects.exclude(slug__in=('wg','rg','ag','rag','team')).values_list('slug',flat=True):
            group = GroupFactory.create(type_id=type_id)
            for user in (None,User.objects.get(username='secretary')):
                ensure_updates_dont_show(group,user)
                ensure_cant_edit(group,user)

    def test_see_status_update(self):
        chair = RoleFactory(name_id='chair',group__type_id='wg')
        GroupEventFactory(type='status_update',group=chair.group)
        for url in group_urlreverse_list(chair.group, 'ietf.group.views.group_about'): 
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            q=PyQuery(response.content)
            self.assertTrue(q('tr#status_update'))
            self.assertTrue(q('tr#status_update td a:contains("Show")'))
            self.assertFalse(q('tr#status_update td a:contains("Edit")'))
            self.client.login(username=chair.person.user.username,password='%s+password'%chair.person.user.username)
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            q=PyQuery(response.content)
            self.assertTrue(q('tr#status_update td a:contains("Show")'))
            self.assertTrue(q('tr#status_update td a:contains("Edit")'))
            self.client.logout()

    def test_view_status_update(self):
        chair = RoleFactory(name_id='chair',group__type_id='wg')
        event = GroupEventFactory(type='status_update',group=chair.group)
        for url in group_urlreverse_list(chair.group, 'ietf.group.views.group_about_status'): 
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            q=PyQuery(response.content)
            self.assertTrue(bleach.linkify(escape(event.desc)) in str(q('pre')))
            self.assertFalse(q('a#edit_button'))
            self.client.login(username=chair.person.user.username,password='%s+password'%chair.person.user.username)
            response = self.client.get(url)
            self.assertEqual(response.status_code,200)
            q=PyQuery(response.content)
            self.assertTrue(q('a#edit_button'))
            self.client.logout()

    def test_edit_status_update(self):
        chair = RoleFactory(name_id='chair',group__type_id='wg')
        event = GroupEventFactory(type='status_update',group=chair.group)
        url = urlreverse('ietf.group.views.group_about_status_edit',kwargs={'acronym':chair.group.acronym}) 
        response = self.client.get(url)
        self.assertEqual(response.status_code,404)
        self.client.login(username=chair.person.user.username,password='%s+password'%chair.person.user.username)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        self.assertTrue(event.desc in q('form textarea#id_content').text())

        response = self.client.post(url,dict(content='Direct content typed into form',submit_response='1'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(chair.group.latest_event(type='status_update').desc,'Direct content typed into form')

        test_file = io.StringIO("This came from a file.")
        test_file.name = "unnamed"
        response = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(chair.group.latest_event(type='status_update').desc,'This came from a file.')

    def test_view_all_status_updates(self):
        area = GroupFactory(type_id='area')
        wg = GroupFactory(type_id='wg',parent=area)
        irtf = GroupFactory(type_id='irtf')
        rg = GroupFactory(type_id='rg',parent=irtf)
        GroupEventFactory(type='status_update',desc='blah blah blah',group=wg)
        GroupEventFactory(type='status_update',desc='blah blah blah',group=rg)
        url = urlreverse('ietf.group.views.all_status')
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_view_status_update_for_meeting(self):
        chair = RoleFactory(name_id='chair',group__type_id='wg')
        GroupEventFactory(type='status_update',group=chair.group)
        sess = SessionFactory.create(meeting__type_id='ietf',group=chair.group,meeting__date=datetime.datetime.today()-datetime.timedelta(days=1))
        url = urlreverse('ietf.group.views.group_about_status_meeting',kwargs={'acronym':chair.group.acronym,'num':sess.meeting.number}) 
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        url = urlreverse('ietf.group.views.group_about_status_meeting',kwargs={'group_type':chair.group.type_id,'acronym':chair.group.acronym,'num':sess.meeting.number}) 
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
       
class GroupParentLoopTests(TestCase):

    def test_group_parent_loop(self):
        mars = GroupFactory(acronym="mars",parent=Group.objects.get(acronym='farfut'))
        test1 = Group.objects.create(
            type_id="team",
            acronym="testteam1",
            name="Test One",
            description="The test team 1 is testing.",
            state_id="active",
            parent = mars,
        )
        test2 = Group.objects.create(
            type_id="team",
            acronym="testteam2",
            name="Test Two",
            description="The test team 2 is testing.",
            state_id="active",
            parent = test1,
        )
        # Change the parent of Mars to make a loop
        mars.parent = test2

        # In face of the loop in the parent links, the code should not loop forever
        import signal

        def timeout_handler(signum, frame):
            raise Exception("Infinite loop in parent links is not handeled properly.")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1)   # One second
        try:
            test2.is_decendant_of("ietf")
        except AssertionError:
            pass
        except Exception:
            raise
        finally:
            signal.alarm(0)

        # If we get here, then there is not an infinite loop
        return

class AcronymValidationTests(TestCase):

    def test_admin_acronym_validation(self):
        now = timezone.now()
        form = AdminGroupForm({'acronym':'shouldpass','name':'should pass','type':'wg','state':'active','used_roles':'[]','time':now})
        self.assertTrue(form.is_valid())
        form = AdminGroupForm({'acronym':'should-fail','name':'should fail','type':'wg','state':'active','used_roles':'[]','time':now})
        self.assertIn('acronym',form.errors)
        form = AdminGroupForm({'acronym':'f','name':'should fail','type':'wg','state':'active','used_roles':'[]','time':now})
        self.assertIn('acronym',form.errors)
        # For the ITU we have a heirarchy of group names that use hyphens as delimeters
        form = AdminGroupForm({'acronym':'should-pass','name':'should pass','type':'sdo','state':'active','used_roles':'[]','time':now})
        self.assertTrue(form.is_valid())
        form = AdminGroupForm({'acronym':'shouldfail-','name':'should fail','type':'wg','state':'active','used_roles':'[]','time':now})
        self.assertIn('acronym',form.errors)
        form = AdminGroupForm({'acronym':'-shouldfail','name':'should fail','type':'wg','state':'active','used_roles':'[]','time':now})
        self.assertIn('acronym',form.errors)

        wg = GroupFactory(acronym='bad-idea', type_id='wg') # There are some existing wg and programs with hyphens in their acronyms.
        form = AdminGroupForm({'acronym':wg.acronym,'name':wg.name,'type':wg.type_id,'state':wg.state_id,'used_roles':str(wg.used_roles),'time':now},instance=wg)
        self.assertTrue(form.is_valid())

    def test_groupform_acronym_validation(self):
        form = GroupForm({'acronym':'shouldpass','name':'should pass','state':'active'},group_type='wg')
        self.assertTrue(form.is_valid())
        form = GroupForm({'acronym':'should-fail','name':'should fail','state':'active'},group_type='wg')
        self.assertIn('acronym',form.errors)
        form = GroupForm({'acronym':'f','name':'should fail','state':'active'},group_type='wg')
        self.assertIn('acronym',form.errors)
        form = GroupForm({'acronym':'should-pass','name':'should pass','state':'active'},group_type='sdo')
        self.assertTrue(form.is_valid())
        form = GroupForm({'acronym':'shouldfail-','name':'should fail','state':'active'},group_type='sdo')
        self.assertIn('acronym',form.errors)
        form = GroupForm({'acronym':'-shouldfail','name':'should fail','state':'active'},group_type='sdo')
        self.assertIn('acronym',form.errors)

        wg = GroupFactory(acronym='bad-idea', type_id='wg') 
        form = GroupForm({'acronym':wg.acronym,'name':wg.name,'state':wg.state_id},group=wg, group_type=wg.type_id)
        self.assertTrue(form.is_valid())

