# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import json

import debug    # pyflakes:ignore

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse as urlreverse
from django.db.models import Q
from django.utils import timezone

from io import StringIO
from pyquery import PyQuery

from ietf.doc.storage_utils import retrieve_str
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.mail import outbox

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.liaisons.factories import ( LiaisonStatementFactory, 
    LiaisonStatementEventFactory, LiaisonStatementAttachmentFactory, RelatedLiaisonStatementFactory)
from ietf.liaisons.models import (LiaisonStatement, LiaisonStatementPurposeName,
    LiaisonStatementAttachment)
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.liaisons.mails import send_sdo_reminder, possibly_send_deadline_reminder
from ietf.liaisons.views import contacts_from_roles, contact_email_from_role
from ietf.utils.timezone import date_today, DEADLINE_TZINFO


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------


def get_liaison_post_data(type='incoming'):
    '''Return a dictionary containing basic liaison entry data'''
    if type == 'incoming':
        from_group = Group.objects.get(acronym='ulm')
        to_group = Group.objects.get(acronym="mars")
    else:
        to_group = Group.objects.get(acronym='ulm')
        from_group = Group.objects.get(acronym="mars")

    return dict(from_groups=str(from_group.pk),
                from_contact='ulm-liaiman@ietf.org',
                to_groups=str(to_group.pk),
                to_contacts='to_contacts@example.com',
                purpose="info",
                title="title",
                submitted_date=timezone.now().strftime("%Y-%m-%d"),
                body="body",
                send="1" )

# -------------------------------------------------
# Test Classes
# -------------------------------------------------

class LiaisonTests(TestCase):
    def test_overview(self):
        liaison = LiaisonStatementFactory()

        r = self.client.get(urlreverse('ietf.liaisons.views.liaison_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

    def test_details(self):
        liaison = LiaisonStatementFactory()

        r = self.client.get(urlreverse("ietf.liaisons.views.liaison_detail", kwargs={ 'object_id': liaison.pk }))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

    def test_feeds(self):
        liaison = LiaisonStatementFactory(title="Comment from United League of Marsmen")

        r = self.client.get('/feed/liaison/recent/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

        r = self.client.get('/feed/liaison/from/%s/' % liaison.from_groups.first().acronym)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

        r = self.client.get('/feed/liaison/to/%s/' % liaison.to_groups.first().acronym)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

        r = self.client.get('/feed/liaison/subject/marsmen/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

    def test_sitemap(self):
        liaison = LiaisonStatementFactory()

        r = self.client.get('/sitemap-liaison.xml')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, urlreverse("ietf.liaisons.views.liaison_detail", kwargs={ 'object_id': liaison.pk }))

    def test_help_pages(self):
        self.assertEqual(self.client.get('/liaison/help/').status_code, 200)
        self.assertEqual(self.client.get('/liaison/help/fields/').status_code, 200)
        self.assertEqual(self.client.get('/liaison/help/from_ietf/').status_code, 200)
        self.assertEqual(self.client.get('/liaison/help/to_ietf/').status_code, 200)


class UnitTests(TestCase):
    def test_get_cc(self):
        from ietf.liaisons.views import get_cc,EMAIL_ALIASES

        # test IETF
        cc = get_cc(Group.objects.get(acronym='ietf'))
        self.assertTrue(EMAIL_ALIASES['IESG'] in cc)
        self.assertTrue(EMAIL_ALIASES['IETFCHAIR'] in cc)
        # test IAB
        cc = get_cc(Group.objects.get(acronym='iab'))
        self.assertTrue(EMAIL_ALIASES['IAB'] in cc)
        self.assertTrue(EMAIL_ALIASES['IABCHAIR'] in cc)
        self.assertTrue(EMAIL_ALIASES['IABEXECUTIVEDIRECTOR'] in cc)
        # test an Area
        area = Group.objects.filter(type='area').first()
        cc = get_cc(area)
        self.assertTrue(EMAIL_ALIASES['IETFCHAIR'] in cc)
        self.assertTrue(contacts_from_roles([area.ad_role()]) in cc)
        # test a Working Group
        wg = Group.objects.filter(type='wg').first()
        cc = get_cc(wg)
        self.assertTrue(contacts_from_roles([wg.parent.ad_role()]) in cc)
        self.assertTrue(contacts_from_roles([wg.get_chair()]) in cc)
        # test an SDO
        sdo = RoleFactory(name_id='liaiman',group__type_id='sdo',).group
        cc = get_cc(sdo)
        self.assertTrue(contacts_from_roles([sdo.role_set.filter(name='liaiman').first()]) in cc)
        # test a cc_contact role
        cc_contact_role = RoleFactory(name_id='liaison_cc_contact', group=sdo)
        cc = get_cc(sdo)
        self.assertIn(contact_email_from_role(cc_contact_role), cc)

    def test_get_contacts_for_group(self):
        from ietf.liaisons.views import get_contacts_for_group, EMAIL_ALIASES

        # test explicit
        sdo = GroupFactory(type_id='sdo')
        contact_email = RoleFactory(name_id='liaison_contact', group=sdo).email.address
        contacts = get_contacts_for_group(sdo)
        self.assertIsNotNone(contact_email)
        self.assertIn(contact_email, contacts)
        # test area
        area = Group.objects.filter(type='area').first()
        contacts = get_contacts_for_group(area)
        self.assertTrue(area.ad_role().email.address in contacts)
        # test wg
        wg = Group.objects.filter(type='wg').first()
        contacts = get_contacts_for_group(wg)
        self.assertTrue(wg.get_chair().email.address in contacts)
        # test ietf
        contacts = get_contacts_for_group(Group.objects.get(acronym='ietf'))
        self.assertTrue(EMAIL_ALIASES['IETFCHAIR'] in contacts)
        # test iab
        contacts = get_contacts_for_group(Group.objects.get(acronym='iab'))
        self.assertTrue(EMAIL_ALIASES['IABCHAIR'] in contacts)
        self.assertTrue(EMAIL_ALIASES['IABEXECUTIVEDIRECTOR'] in contacts)
        # test iesg
        contacts = get_contacts_for_group(Group.objects.get(acronym='iesg'))
        self.assertTrue(EMAIL_ALIASES['IESG'] in contacts)

    def test_needs_approval(self):
        from ietf.liaisons.views import needs_approval

        group = Group.objects.get(acronym='ietf')
        self.assertFalse(needs_approval(group,group.get_chair().person))
        group = Group.objects.get(acronym='iab')
        self.assertFalse(needs_approval(group,group.get_chair().person))
        area = Group.objects.filter(type='area').first()
        self.assertFalse(needs_approval(area,area.ad_role().person))
        wg = Group.objects.filter(type='wg').first()
        self.assertFalse(needs_approval(wg,wg.parent.ad_role().person))

    def test_approvable_liaison_statements(self):
        source_wg = RoleFactory(name_id='ad',group__type_id='wg').group
        LiaisonStatementFactory(from_groups = [ source_wg, ], to_groups = [ GroupFactory(type_id='sdo'), ])
        from ietf.liaisons.utils import approvable_liaison_statements

        outgoing = LiaisonStatement.objects.filter(to_groups__type='sdo').first()
        outgoing.set_state('pending')
        user = outgoing.from_groups.first().ad_role().person.user
        qs = approvable_liaison_statements(user)
        self.assertEqual(len(qs),1)
        self.assertEqual(qs[0].pk,outgoing.pk)


class AjaxTests(TestCase):
    def test_ajax(self):
        LiaisonStatementFactory() # This test needs improvement. It passes without this object present.
        url = urlreverse('ietf.liaisons.views.ajax_get_liaison_info') + "?to_groups=&from_groups="
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["error"], False)
        self.assertEqual(data["post_only"], False)
        self.assertTrue('cc' in data)
        self.assertTrue('needs_approval' in data)
        self.assertTrue('to_contacts' in data)
        self.assertTrue('response_contacts' in data)

    def test_ajax_to_contacts(self):
        area = RoleFactory(name_id='ad',group__type_id='area').group
        group = GroupFactory(parent=area)
        LiaisonStatementFactory(to_groups=[group,])
        contact_email = contact_email_from_role(RoleFactory(name_id='liaison_contact', group=group))

        url = urlreverse('ietf.liaisons.views.ajax_get_liaison_info') + "?to_groups={}&from_groups=".format(group.pk)
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["to_contacts"],[contact_email])

    def test_ajax_select2_search_liaison_statements(self):
        liaison = LiaisonStatementFactory()

        # test text search
        url = urlreverse('ietf.liaisons.views.ajax_select2_search_liaison_statements') + "?q=%s" % liaison.title[:5]
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(liaison.pk in [ x['id'] for x in data ])

        # test id search
        url = urlreverse('ietf.liaisons.views.ajax_select2_search_liaison_statements') + "?q=%s" % liaison.pk
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(liaison.pk in [ x['id'] for x in data ])


class ManagementCommandTests(TestCase):
    def test_check_liaison_deadlines(self):
        from django.core.management import call_command

        LiaisonStatementFactory(deadline=date_today(DEADLINE_TZINFO)+datetime.timedelta(days=1))

        out = io.StringIO()
        mailbox_before = len(outbox)
        call_command('check_liaison_deadlines',stdout=out)
        self.assertEqual(len(outbox), mailbox_before + 1)

    def test_remind_update_sdo_list(self):
        from django.core.management import call_command

        RoleFactory(name_id='liaiman',group__type_id='sdo')

        out = io.StringIO()
        mailbox_before = len(outbox)
        call_command('remind_update_sdo_list',stdout=out)
        self.assertTrue(len(outbox) > mailbox_before)


class LiaisonManagementTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['LIAISON_ATTACH_PATH']

    def test_add_restrictions(self):
        # incoming restrictions
        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_add_comment(self):
        liaison = LiaisonStatementFactory()
        
        # test unauthorized
        addurl = urlreverse('ietf.liaisons.views.add_comment',kwargs=dict(object_id=liaison.pk))
        url = urlreverse('ietf.liaisons.views.liaison_history',kwargs=dict(object_id=liaison.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Add Comment')")), 0)
        login_testing_unauthorized(self, "secretary", addurl)

        # login in as secretariat staff
        self.client.login(username="secretary", password="secretary+password")

        # Check add_comment page
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("h1:contains('Add comment')")), 1)
        self.assertEqual(len(q("form div label:contains('Comment')")), 1)
        self.assertEqual(len(q("form textarea")), 1)
        self.assertEqual(len(q("form button.btn:contains('Add Comment')")), 1)

        # public comment
        comment = 'Test comment'
        r = self.client.post(addurl, dict(comment=comment))
        self.assertEqual(r.status_code,302)
        qs = liaison.liaisonstatementevent_set.filter(type='comment',desc=comment)
        self.assertTrue(qs.count(),1)
        
        # private comment
        r = self.client.post(addurl, dict(comment='Private comment',private=True),follow=True)
        self.assertEqual(r.status_code,200)
        self.assertContains(r, 'Private comment')
        self.client.logout()
        r = self.client.get(url)
        self.assertNotContains(r, 'Private comment')

    def test_taken_care_of(self):
        liaison = LiaisonStatementFactory(deadline=date_today(DEADLINE_TZINFO)+datetime.timedelta(days=1))

        url = urlreverse('ietf.liaisons.views.liaison_detail', kwargs=dict(object_id=liaison.pk))
        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form button[name=do_action_taken]')), 0)

        # log in and get
        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form button[name=do_action_taken]')), 1)

        # mark action taken
        r = self.client.post(url, dict(do_action_taken="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form button[name=do_action_taken]')), 0)
        liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertTrue(liaison.action_taken)

    def test_approval_process(self):
        # must be outgoing liaison to need approval
        liaison = LiaisonStatementFactory(
            state_id = 'pending',
            from_groups = [GroupFactory(type_id='wg'),],
            to_groups = [RoleFactory(name_id='liaiman', person__user__username='ulm-liaiman', group__type_id='sdo').group],
        )

        # check the overview page
        url = urlreverse('ietf.liaisons.views.liaison_list', kwargs=dict(state='pending'))
        login_testing_unauthorized(self, "ad", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)

        # check the detail page / unauthorized
        url = urlreverse('ietf.liaisons.views.liaison_detail', kwargs=dict(object_id=liaison.pk))
        self.client.logout()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form button[name=approved]')), 0)

        # check the detail page / authorized
        self.client.login(username="ulm-liaiman", password="ulm-liaiman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, liaison.title)
        q = PyQuery(r.content)
        from ietf.liaisons.utils import can_edit_liaison
        user = User.objects.get(username='ulm-liaiman')
        self.assertTrue(can_edit_liaison(user, liaison))
        self.assertEqual(len(q('form button[name=approved]')), 1)

        # approve
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(approved="1"))
        self.assertEqual(r.status_code, 200)

        liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertTrue(liaison.approved)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])
        # ensure events created
        self.assertTrue(liaison.liaisonstatementevent_set.filter(type='approved'))
        self.assertTrue(liaison.liaisonstatementevent_set.filter(type='posted'))

    def test_edit_liaison(self):
        liaison = LiaisonStatementFactory(deadline=date_today(DEADLINE_TZINFO) + datetime.timedelta(days=1))
        LiaisonStatementEventFactory(statement=liaison,type_id='submitted', time=timezone.now()-datetime.timedelta(days=1))
        LiaisonStatementEventFactory(statement=liaison,type_id='posted')
        from_group = liaison.from_groups.first()
        to_group = liaison.to_groups.first()
        rel1 = RelatedLiaisonStatementFactory(source=liaison)
        rel2 = RelatedLiaisonStatementFactory(source=liaison)

        url = urlreverse('ietf.liaisons.views.liaison_edit', kwargs=dict(object_id=liaison.pk))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form input[name=from_contact]')), 1)
        json_data = q('form select[name=related_to]').attr('data-pre')
        try:
            decoded = json.loads(json_data)
        except json.JSONDecodeError as e:
            self.fail('data-pre contained invalid JSON data: %s' % str(e))
        decoded_ids = [item['id'] for item in decoded]
        self.assertEqual(decoded_ids, [rel1.target.id, rel2.target.id])

        # edit
        attachments_before = liaison.attachments.count()
        test_content = "hello world"
        test_file = StringIO(test_content)
        test_file.name = "unnamed"
        r = self.client.post(url,
                             dict(from_groups=str(from_group.pk),
                                  from_contact=liaison.from_contact,
                                  to_groups=str(to_group.pk),
                                  to_contacts="to_poc@example.com",
                                  technical_contacts="technical_contact@example.com",
                                  cc_contacts="cc@example.com",
                                  purpose="action",
                                  deadline=(liaison.deadline + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  title="title",
                                  submitted_date=(liaison.posted + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  ))
        self.assertEqual(r.status_code, 302)

        new_liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertEqual(new_liaison.from_groups.first(), from_group)
        self.assertEqual(new_liaison.to_groups.first(), to_group)
        self.assertEqual(new_liaison.to_contacts, "to_poc@example.com")
        self.assertEqual(new_liaison.technical_contacts, "technical_contact@example.com")
        self.assertEqual(new_liaison.cc_contacts, "cc@example.com")
        self.assertEqual(new_liaison.purpose, LiaisonStatementPurposeName.objects.get(slug='action'))
        self.assertEqual(new_liaison.deadline, liaison.deadline + datetime.timedelta(days=1)),
        self.assertEqual(new_liaison.title, "title")
        #self.assertEqual(new_liaison.submitted.date(), (liaison.submitted + datetime.timedelta(days=1)).date())
        self.assertEqual(new_liaison.body, "body")
        # ensure events created
        self.assertTrue(liaison.liaisonstatementevent_set.filter(type='modified'))

        self.assertEqual(new_liaison.attachments.count(), attachments_before + 1)
        attachment = new_liaison.attachments.order_by("-name")[0]
        self.assertEqual(attachment.title, "attachment")
        with (Path(settings.LIAISON_ATTACH_PATH) / attachment.uploaded_filename).open() as f:
            written_content = f.read()
        self.assertEqual(written_content, test_content)
        self.assertEqual(
            retrieve_str(attachment.type_id, attachment.uploaded_filename),
            test_content,
        )


    def test_incoming_access(self):
        '''Ensure only Secretariat, Liaison Managers, and Authorized Individuals
        have access to incoming liaisons.
        '''
        sdo = RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman').group
        RoleFactory(name_id='auth',group=sdo,person__user__username='ulm-auth')
        stmt = LiaisonStatementFactory(from_groups=[sdo,])
        LiaisonStatementEventFactory(statement=stmt,type_id='posted')
        RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars')
        url = urlreverse('ietf.liaisons.views.liaison_list')
        addurl = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})

        # public user no access
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New incoming liaison')")), 0)
        r = self.client.get(addurl)
        self.assertRedirects(r,settings.LOGIN_URL + '?next=/liaison/add/incoming/')

        # regular Chair no access
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New incoming liaison')")), 0)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 403)

        # Liaison Manager has access
        self.client.login(username="ulm-liaiman", password="ulm-liaiman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('a.btn:contains("New incoming liaison")')), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # Authorized Individual has access
        self.client.login(username="ulm-auth", password="ulm-auth+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New incoming liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New incoming liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

    def test_outgoing_access(self):

        sdo = RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman').group
        RoleFactory(name_id='auth',group=sdo,person__user__username='ulm-auth')
        mars = RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars').group
        RoleFactory(name_id='secr',group=mars,person__user__username='mars-secr')
        RoleFactory(name_id='execdir',group=Group.objects.get(acronym='iab'),person__user__username='iab-execdir')

        url = urlreverse('ietf.liaisons.views.liaison_list')
        addurl = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'outgoing'})

        # public user no access
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 0)
        r = self.client.get(addurl)
        self.assertRedirects(r,settings.LOGIN_URL + '?next=/liaison/add/outgoing/')

        # AD has access
        self.assertTrue(self.client.login(username="ad", password="ad+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # WG Chair has access
        self.assertTrue(self.client.login(username="marschairman", password="marschairman+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # WG Secretary has access
        self.assertTrue(self.client.login(username="mars-secr", password="mars-secr+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # IETF Chair has access
        self.assertTrue(self.client.login(username="ietf-chair", password="ietf-chair+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # IAB Chair has access
        self.assertTrue(self.client.login(username="iab-chair", password="iab-chair+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # IAB Executive Director
        self.assertTrue(self.client.login(username="iab-execdir", password="iab-execdir+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # Liaison Manager has access
        self.assertTrue(self.client.login(username="ulm-liaiman", password="ulm-liaiman+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('a.btn:contains("New outgoing liaison")')), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

        # Authorized Individual has no access
        self.assertTrue(self.client.login(username="ulm-auth", password="ulm-auth+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 0)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 403)

        # Secretariat has access
        self.assertTrue(self.client.login(username="secretary", password="secretary+password"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('New outgoing liaison')")), 1)
        r = self.client.get(addurl)
        self.assertEqual(r.status_code, 200)

    def test_incoming_options(self):
        '''Check from_groups, to_groups options for different user classes'''

        RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman')

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})

        # get count of all IETF entities for to_group options
        top = Q(acronym__in=('ietf','iesg','iab'))
        areas = Q(type_id='area',state='active')
        wgs = Q(type_id='wg',state='active')
        all_entity_count = Group.objects.filter(top|areas|wgs).count()

        # Regular user
        # from_groups = groups for which they are Liaison Manager or Authorized Individual
        # to_groups = all IETF entities
        login_testing_unauthorized(self, "ulm-liaiman", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('select#id_from_groups option')), 1)
        self.assertEqual(len(q('select#id_to_groups option')), all_entity_count)

        # Secretariat
        # from_groups = all active SDOs
        # to_groups = all IETF entities
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        all_sdos = Group.objects.filter(type_id='sdo',state='active').count()
        self.assertEqual(len(q('select#id_from_groups option')), all_sdos)
        self.assertEqual(len(q('select#id_to_groups option')), all_entity_count)

    def test_outgoing_options(self):
        RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman')
        RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars')

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'outgoing'})

        # get count of all IETF entities for to_group options
        top = Q(acronym__in=('ietf','iesg','iab'))
        areas = Q(type_id='area',state='active')
        wgs = Q(type_id='wg',state='active')
        all_entity_count = Group.objects.filter(top|areas|wgs).count()

        # Regular user (Chair, AD)
        # from_groups = limited by role
        # to_groups = all SDOs
        person = Person.objects.filter(role__name='chair',role__group__acronym='mars').first()
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        groups = Group.objects.filter(role__person=person,role__name='chair',state='active',type='wg')
        all_sdos = Group.objects.filter(state='active',type='sdo')
        self.assertEqual(len(q('select#id_from_groups option')), groups.count())
        self.assertEqual(len(q('select#id_to_groups option')), all_sdos.count())

        # Liaison Manager
        # from_groups =
        # to_groups = limited to managed group

        # Secretariat
        # from_groups = all IETF entities
        # to_groups = all active SDOs
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        all_sdos = Group.objects.filter(type_id='sdo',state='active').count()
        self.assertEqual(len(q('select#id_from_groups option')), all_entity_count)
        self.assertEqual(len(q('select#id_to_groups option')), all_sdos)


    def test_add_incoming_liaison(self):
        sdo = RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman').group
        GroupFactory(type_id='sdo') # This test assumes there are two sdo groups in the database
        wg = RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars').group
        liaison = LiaisonStatementFactory(from_groups=[wg,],to_groups=[sdo,])

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=body]')), 1)

        # add new
        mailbox_before = len(outbox)
        test_content = "hello world"
        test_file = StringIO(test_content)
        test_file.name = "unnamed"
        from_groups = [ str(g.pk) for g in Group.objects.filter(type="sdo") ]
        to_group = Group.objects.get(acronym="mars")
        submitter = Person.objects.get(user__username="marschairman")
        today = date_today(datetime.timezone.utc)
        related_liaison = liaison
        r = self.client.post(url,
                             dict(from_groups=from_groups,
                                  from_contact=submitter.email_address(),
                                  to_groups=[str(to_group.pk)],
                                  to_contacts='to_contacts@example.com',
                                  technical_contacts="technical_contact@example.com",
                                  action_holder_contacts="action_holder_contacts@example.com",
                                  cc_contacts="cc@example.com",
                                  purpose="action",
                                  deadline=(today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  other_identifiers="IETF-1234",
                                  related_to=str(related_liaison.pk),
                                  title="title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  send="1",
                                  ))
        self.assertEqual(r.status_code, 302)

        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertEqual(l.from_groups.count(),2)
        self.assertEqual(l.from_contact.address, submitter.email_address())
        self.assertSequenceEqual(l.to_groups.all(),[to_group])
        self.assertEqual(l.technical_contacts, "technical_contact@example.com")
        self.assertEqual(l.action_holder_contacts, "action_holder_contacts@example.com")
        self.assertEqual(l.cc_contacts, "cc@example.com")
        self.assertEqual(l.purpose, LiaisonStatementPurposeName.objects.get(slug='action'))
        self.assertEqual(l.deadline, today + datetime.timedelta(days=1)),
        self.assertEqual(l.other_identifiers, "IETF-1234"),
        self.assertEqual(l.source_of_set.first().target,liaison),
        self.assertEqual(l.title, "title")
        self.assertEqual(l.submitted.date(), today)
        self.assertEqual(l.body, "body")
        self.assertEqual(l.state.slug, 'posted')
        # ensure events created
        self.assertTrue(l.liaisonstatementevent_set.filter(type='submitted'))
        self.assertTrue(l.liaisonstatementevent_set.filter(type='posted'))

        self.assertEqual(l.attachments.count(), 1)
        attachment = l.attachments.all()[0]
        self.assertEqual(attachment.title, "attachment")
        with (Path(settings.LIAISON_ATTACH_PATH) / attachment.uploaded_filename).open() as f:
            written_content = f.read()
        self.assertEqual(written_content, test_content)
        self.assertEqual(
            retrieve_str(attachment.type_id, attachment.uploaded_filename),
            test_content
        )

        test_file.seek(0)
        self.assertEqual(written_content, test_file.read())

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])
    
        self.assertTrue('to_contacts@' in outbox[-1]['To'])
        self.assertTrue('cc@' in outbox[-1]['Cc'])

    def test_add_outgoing_liaison(self):
        RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman')
        wg = RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars').group
        RoleFactory(name_id='ad',person=Person.objects.get(user__username='ad'),group=wg)
        liaison = LiaisonStatementFactory()

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'outgoing'})
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=body]')), 1)

        # add new
        mailbox_before = len(outbox)
        test_content = "hello world"
        test_file = StringIO(test_content)
        test_file.name = "unnamed"
        from_group = Group.objects.get(acronym="mars")
        to_group = Group.objects.filter(type="sdo")[0]
        submitter = Person.objects.get(user__username="marschairman")
        today = date_today(datetime.timezone.utc)
        related_liaison = liaison
        r = self.client.post(url,
                             dict(from_groups=str(from_group.pk),
                                  from_contact=submitter.email_address(),
                                  to_groups=str(to_group.pk),
                                  to_contacts='to_contacts@example.com',
                                  approved="",
                                  technical_contacts="technical_contact@example.com",
                                  cc_contacts="cc@example.com",
                                  purpose="action",
                                  deadline=(today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  other_identifiers="IETF-1234",
                                  related_to=str(related_liaison.pk),
                                  title="title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  send="1",
                                  ))
        self.assertEqual(r.status_code, 302)

        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertSequenceEqual(l.from_groups.all(), [from_group])
        self.assertEqual(l.from_contact.address, submitter.email_address())
        self.assertSequenceEqual(l.to_groups.all(), [to_group])
        self.assertEqual(l.to_contacts, "to_contacts@example.com")
        self.assertEqual(l.technical_contacts, "technical_contact@example.com")
        self.assertEqual(l.cc_contacts, "cc@example.com")
        self.assertEqual(l.purpose, LiaisonStatementPurposeName.objects.get(slug='action'))
        self.assertEqual(l.deadline, today + datetime.timedelta(days=1)),
        self.assertEqual(l.other_identifiers, "IETF-1234"),
        self.assertEqual(l.source_of_set.first().target,liaison),
        self.assertEqual(l.title, "title")
        self.assertEqual(l.submitted.date(), today)
        self.assertEqual(l.body, "body")
        self.assertEqual(l.state.slug,'pending')
        # ensure events created
        self.assertTrue(l.liaisonstatementevent_set.filter(type='submitted'))
        self.assertFalse(l.liaisonstatementevent_set.filter(type='posted'))

        self.assertEqual(l.attachments.count(), 1)
        attachment = l.attachments.all()[0]
        self.assertEqual(attachment.title, "attachment")
        with (Path(settings.LIAISON_ATTACH_PATH) / attachment.uploaded_filename).open() as f:
            written_content = f.read()
        self.assertEqual(written_content, test_content)
        self.assertEqual(
            retrieve_str(attachment.type_id, attachment.uploaded_filename),
            test_content
        )

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])
        self.assertTrue('aread@' in outbox[-1]['To'])

    def test_add_outgoing_liaison_unapproved_post_only(self):
        RoleFactory(name_id='liaiman',group__type_id='sdo', person__user__username='ulm-liaiman')
        mars = RoleFactory(name_id='chair',person__user__username='marschairman',group__acronym='mars').group
        RoleFactory(name_id='ad',group=mars)

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'outgoing'})
        login_testing_unauthorized(self, "secretary", url)

        # add new
        mailbox_before = len(outbox)
        from_group = Group.objects.get(acronym="mars")
        to_group = Group.objects.filter(type="sdo")[0]
        submitter = Person.objects.get(user__username="marschairman")
        today = date_today(datetime.timezone.utc)
        r = self.client.post(url,
                             dict(from_groups=str(from_group.pk),
                                  from_contact=submitter.email_address(),
                                  to_groups=str(to_group.pk),
                                  to_contacts='to_contacts@example.com',
                                  approved="",
                                  purpose="info",
                                  title="title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  post_only="1",
                                  ))
        self.assertEqual(r.status_code, 302)
        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertEqual(l.state.slug,'pending')
        self.assertEqual(len(outbox), mailbox_before + 1)

    def test_liaison_add_attachment(self):
        liaison = LiaisonStatementFactory(deadline=date_today(DEADLINE_TZINFO)+datetime.timedelta(days=1))
        LiaisonStatementEventFactory(statement=liaison,type_id='submitted')

        self.assertEqual(liaison.attachments.count(),0)


        # get minimum edit post data
        test_data = "dummy file"
        file = StringIO(test_data)
        file.name = "upload.txt"
        post_data = dict(
            from_groups = ','.join([ str(x.pk) for x in liaison.from_groups.all() ]),
            from_contact = liaison.from_contact.address,
            to_groups = ','.join([ str(x.pk) for x in liaison.to_groups.all() ]),
            to_contacts = 'to_contacts@example.com',
            purpose = liaison.purpose.slug,
            deadline = liaison.deadline,
            title = liaison.title,
            submitted_date = liaison.submitted.strftime('%Y-%m-%d'),
            body = liaison.body,
            attach_title_1 = 'Test Attachment',
            attach_file_1 = file,
        )

        url = urlreverse('ietf.liaisons.views.liaison_edit', kwargs=dict(object_id=liaison.pk))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.post(url,post_data)
        #if r.status_code != 302:
        #    q = PyQuery(r.content)
        #    print(q('div.is-invalid div.alert').text())
        #    print r.content
        self.assertEqual(r.status_code, 302)
        self.assertEqual(liaison.attachments.count(),1)
        event = liaison.liaisonstatementevent_set.order_by('id').last()
        self.assertTrue(event.desc.startswith('Added attachment'))
        attachment = liaison.attachments.get()
        self.assertEqual(
            retrieve_str(attachment.type_id, attachment.uploaded_filename),
            test_data
        )

    def test_liaison_edit_attachment(self):

        attachment = LiaisonStatementAttachmentFactory(document__name='liaiatt-1')
        url = urlreverse('ietf.liaisons.views.liaison_edit_attachment', kwargs=dict(object_id=attachment.statement_id,doc_id=attachment.document_id))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        post_data = dict(title='New Title')
        r = self.client.post(url,post_data)
        attachment = LiaisonStatementAttachment.objects.get(pk=attachment.pk)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(attachment.document.title,'New Title')

    def test_liaison_delete_attachment(self):
        attachment = LiaisonStatementAttachmentFactory(document__name='liaiatt-1')
        liaison = attachment.statement
        url = urlreverse('ietf.liaisons.views.liaison_delete_attachment', kwargs=dict(object_id=liaison.pk,attach_id=attachment.pk))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(liaison.liaisonstatementattachment_set.filter(removed=False).count(),0)

    def test_in_response(self):
        '''A statement with purpose=in_response must have related statement specified'''
        GroupFactory(type_id='wg',acronym='mars')
        GroupFactory(type_id='sdo',acronym='ulm')

        url = urlreverse('ietf.liaisons.views.liaison_add',kwargs=dict(type='incoming'))
        login_testing_unauthorized(self, "secretary", url)
        data = get_liaison_post_data()
        data['purpose'] = 'response'
        r = self.client.post(url,data)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(q("form .is-invalid"))

    def test_liaison_history(self):
        liaison = LiaisonStatementFactory()

        url = urlreverse('ietf.liaisons.views.liaison_history',kwargs=dict(object_id=liaison.pk))
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        event_count = liaison.liaisonstatementevent_set.count()
        self.assertEqual(len(q('tr')),event_count + 1)  # +1 for header row

    def test_resend_liaison(self):
        liaison = LiaisonStatementFactory()

        url = urlreverse('ietf.liaisons.views.liaison_resend',kwargs=dict(object_id=liaison.pk))
        login_testing_unauthorized(self, "secretary", url)

        mailbox_before = len(outbox)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue(liaison.liaisonstatementevent_set.filter(type='resent'))

    def test_kill_liaison(self):
        mars = GroupFactory(type_id='wg',acronym='mars')
        sdo = GroupFactory(type_id='sdo')
        liaison = LiaisonStatementFactory(from_groups=[mars,], to_groups=[sdo,], state_id='pending')
        # must be outgoing liaison to need approval
        liaison.from_groups.clear()
        liaison.from_groups.add(Group.objects.get(acronym="mars"))
        liaison.set_state('pending')

        url = urlreverse('ietf.liaisons.views.liaison_detail', kwargs=dict(object_id=liaison.pk))
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, dict(dead="1"))
        self.assertEqual(r.status_code, 200)

        # need to reacquire object to check current state
        liaison = LiaisonStatement.objects.get(pk=liaison.pk)
        self.assertEqual(liaison.state.slug,'dead')
        self.assertTrue(liaison.liaisonstatementevent_set.filter(type='killed'))

    def test_dead_view(self):
        LiaisonStatementFactory(state_id='dead')

        url = urlreverse('ietf.liaisons.views.liaison_list', kwargs=dict(state='dead'))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        dead_liaison_count = LiaisonStatement.objects.filter(state='dead').count()
        self.assertEqual(len(q('tr')),dead_liaison_count + 1)  # +1 for header row

    def test_liaison_reply(self):
        sdo = RoleFactory(name_id='liaiman',person__user__username='ulm-liaiman',group__type_id='sdo').group
        liaison = LiaisonStatementFactory(from_groups=[sdo,])

        # unauthorized, no reply to button
        url = urlreverse('ietf.liaisons.views.liaison_detail', kwargs=dict(object_id=liaison.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Reply to liaison')")), 0)

        # authorized
        self.client.login(username="ulm-liaiman", password="ulm-liaiman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Reply to liaison')")), 1)

        # check form initial values
        url = urlreverse('ietf.liaisons.views.liaison_reply', kwargs=dict(object_id=liaison.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        reply_to_group_id = str(liaison.from_groups.first().pk)
        reply_from_group_id = str(liaison.to_groups.first().pk)
        self.assertEqual(q('#id_from_groups').find('option:selected').val(),reply_from_group_id)
        self.assertEqual(q('#id_to_groups').find('option:selected').val(),reply_to_group_id)
        pre = json.loads(q('#id_related_to').attr("data-pre"))
        self.assertEqual(pre[0]['id'], liaison.pk)

    def test_search(self):
        # Statement 1
        LiaisonStatementEventFactory(type_id='posted', statement__body="Has recently in its body",statement__from_groups=[GroupFactory(type_id='sdo',acronym='ulm'),])
        # Statement 2
        s2 = LiaisonStatementEventFactory(type_id='posted', statement__body="That word does not occur here", statement__title="Nor does it occur here")
        s2.time=datetime.datetime(2010, 1, 1, tzinfo=datetime.timezone.utc)
        s2.save()

        # test list only, no search filters
        url = urlreverse('ietf.liaisons.views.liaison_list')
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(q('tr')),3)        # two results

        # test 0 results
        url = urlreverse('ietf.liaisons.views.liaison_list') + "?text=gobbledygook&source=&destination=&start_date=&end_date="
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(q('tr')),0)        # no results

        # test body text
        # The view being tested looks for the word "recently" in several fields
        # The test data right now constrains the second statement's body and title to not contain that word
        # if the factories start generating in the other places it looks (see SearchLiaisonForm), this test
        # will need to be smarter about inspecting or further constraining the test objects. 
        url = urlreverse('ietf.liaisons.views.liaison_list') + "?text=recently&source=&destination=&start_date=&end_date="
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(q('tr')),2)        # one result

        # test from group
        url = urlreverse('ietf.liaisons.views.liaison_list') + "?text=&source=ulm&destination=&start_date=&end_date="
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(q('tr')),2)        # one result

        # test start date
        url = urlreverse('ietf.liaisons.views.liaison_list') + "?text=&source=&destination=&start_date=2015-01-01&end_date="
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(q('tr')),2)        # one result

    # -------------------------------------------------
    # Test Redirects
    # -------------------------------------------------
    def test_redirect_add(self):
        self.client.login(username="secretary", password="secretary+password")
        url = urlreverse('ietf.liaisons.views.redirect_add')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

    def test_redirect_for_approval(self):
        liaison = LiaisonStatementFactory(state_id='pending')

        self.client.login(username="secretary", password="secretary+password")
        url = urlreverse('ietf.liaisons.views.redirect_for_approval')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        url = urlreverse('ietf.liaisons.views.redirect_for_approval', kwargs={'object_id':liaison.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

    # -------------------------------------------------
    # Form validations
    # -------------------------------------------------
    def test_post_and_send_fail(self):
        RoleFactory(name_id='liaiman',person__user__username='ulm-liaiman',group__type_id='sdo',group__acronym='ulm')
        GroupFactory(type_id='wg',acronym='mars')

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})
        login_testing_unauthorized(self, "ulm-liaiman", url)

        r = self.client.post(url,get_liaison_post_data(),follow=True)

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'As an IETF Liaison Manager you can not send incoming liaison statements')

    def test_deadline_field(self):
        '''Required for action, comment, not info, response'''
        pass

    def test_email_validations(self):
        GroupFactory(type_id='sdo', acronym='ulm')
        GroupFactory(type_id='wg', acronym='mars')

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})
        login_testing_unauthorized(self, "secretary", url)

        post_data = get_liaison_post_data()
        post_data['from_contact'] = 'bademail'
        post_data['to_contacts'] = 'bademail'
        post_data['technical_contacts'] = 'bad_email'
        post_data['action_holder_contacts'] = 'bad_email'
        post_data['cc_contacts'] = 'bad_email'
        r = self.client.post(url,post_data,follow=True)

        q = PyQuery(r.content)
        self.assertEqual(r.status_code, 200)
        result = q('#id_technical_contacts').parent().parent('.is-invalid')
        result = q('#id_action_holder_contacts').parent().parent('.is-invalid')
        result = q('#id_cc_contacts').parent().parent('.is-invalid')
        self.assertEqual(len(result), 1)

    def test_body_or_attachment(self):
        GroupFactory(type_id='sdo', acronym='ulm')
        GroupFactory(type_id='wg', acronym='mars')

        url = urlreverse('ietf.liaisons.views.liaison_add', kwargs={'type':'incoming'})
        login_testing_unauthorized(self, "secretary", url)

        post_data = get_liaison_post_data()
        post_data['body'] = ''
        r = self.client.post(url,post_data,follow=True)

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'You must provide a body or attachment files')

    def test_send_sdo_reminder(self):
        RoleFactory(name_id='liaiman',person__user__username='ulm-liaiman',person__user__email='ulm-liaiman@somewhere.example',group__type_id='sdo',group__acronym='ulm')

        mailbox_before = len(outbox)
        send_sdo_reminder(Group.objects.filter(type="sdo")[0])
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("authorized individuals" in outbox[-1]["Subject"])
        self.assertTrue('ulm-liaiman@' in outbox[-1]['To'])

    def test_send_liaison_deadline_reminder(self):
        liaison = LiaisonStatementFactory(deadline=date_today(DEADLINE_TZINFO) + datetime.timedelta(days=1))

        mailbox_before = len(outbox)
        possibly_send_deadline_reminder(liaison)
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("deadline" in outbox[-1]["Subject"])

        # try pushing the deadline
        liaison.deadline = liaison.deadline + datetime.timedelta(days=30)
        liaison.save()

        mailbox_before = len(outbox)
        possibly_send_deadline_reminder(liaison)
        self.assertEqual(len(outbox), mailbox_before)
