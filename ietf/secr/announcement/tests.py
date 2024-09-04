# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from pyquery import PyQuery

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.group.factories import RoleFactory
from ietf.group.models import Group
from ietf.message.models import Message
from ietf.name.models import RoleName
from ietf.nomcom.test_data import nomcom_test_data
from ietf.message.models import AnnouncementFrom
from ietf.utils.mail import outbox, empty_outbox

SECR_USER='secretary'
WG_USER=''
AD_USER=''

class SecrAnnouncementTestCase(TestCase):
    def setUp(self):
        super().setUp()
        chair = RoleName.objects.get(slug='chair')
        secr = RoleName.objects.get(slug='secr')
        ietf = Group.objects.get(acronym='ietf')
        iab = Group.objects.get(acronym='iab')
        secretariat = Group.objects.get(acronym='secretariat')
        AnnouncementFrom.objects.create(name=secr,group=secretariat,address='IETF Secretariat <ietf-secretariat@ietf.org>')
        AnnouncementFrom.objects.create(name=chair,group=ietf,address='IETF Chair <chair@ietf.org>')
        AnnouncementFrom.objects.create(name=chair,group=iab,address='IAB Chair <iab-chair@iab.org>')

    def test_main(self):
        "Main Test"
        url = reverse('ietf.secr.announcement.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
    
    def test_main_announce_from(self):
        url = reverse('ietf.secr.announcement.views.main')

        # Secretariat
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#id_frm option')),4)

        # IAB Chair
        self.client.login(username="iab-chair", password="iab-chair+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#id_frm option')),1)
        self.assertTrue('<iab-chair@iab.org>' in q('#id_frm option').val())

        # IETF Chair
        self.client.login(username="ietf-chair", password="ietf-chair+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#id_frm option')),1)
        self.assertTrue('<chair@ietf.org>' in q('#id_frm option').val())

class UnauthorizedAnnouncementCase(TestCase):
    def test_unauthorized(self):
        "Unauthorized Test"
        url = reverse('ietf.secr.announcement.views.main')
        person = RoleFactory(name_id='chair',group__acronym='mars').person
        self.client.login(username=person.user.username, password=person.user.username+"+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
    
class SubmitAnnouncementCase(TestCase):
    def test_invalid_submit(self):
        "Invalid Submit"
        url = reverse('ietf.secr.announcement.views.main')
        post_data = {'id_subject':''}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
    def test_valid_submit(self):
        "Valid Submit"
        nomcom_test_data()
        empty_outbox()
        url = reverse('ietf.secr.announcement.views.main')
        confirm_url = reverse('ietf.secr.announcement.views.confirm')
        nomcom = Group.objects.get(type='nomcom')
        post_data = {'nomcom': nomcom.pk,
                     'to':'Other...',
                     'to_custom':'rcross@amsl.com',
                     'frm':'IETF Secretariat &lt;ietf-secretariat@ietf.org&gt;',
                     'reply_to':'secretariat@ietf.org',
                     'subject':'Test Subject',
                     'body':'This is a test.'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertContains(response, 'Confirm Announcement')
        response = self.client.post(confirm_url,post_data,follow=True)
        self.assertRedirects(response, url)
        self.assertEqual(len(outbox),1)
        self.assertEqual(outbox[0]['subject'],'Test Subject')
        self.assertEqual(outbox[0]['to'],'<rcross@amsl.com>')
        message = Message.objects.filter(by__user__username='secretary').last()
        self.assertEqual(message.subject,'Test Subject')
        self.assertTrue(nomcom in message.related_groups.all())
