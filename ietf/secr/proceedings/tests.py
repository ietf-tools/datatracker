# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug                            # pyflakes:ignore
import io
import json
import os

from django.conf import settings
from django.urls import reverse
from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.utils.test_utils import TestCase


from ietf.secr.proceedings.proc_utils import _get_session, _get_urls_from_json


class ProceedingsTestCase(TestCase):
    def test_main(self):
        "Main Test"
        MeetingFactory(type_id='ietf')
        RoleFactory(name_id='chair',person__user__username='marschairman')
        url = reverse('ietf.secr.proceedings.views.main')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # test chair access
        self.client.logout()
        self.client.login(username="marschairman", password="marschairman+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class VideoRecordingTestCase(TestCase):

    def test_get_session(self):
        session = SessionFactory()
        meeting = session.meeting
        number = meeting.number
        name = session.group.acronym
        ts_time = session.official_timeslotassignment().timeslot.local_start_time()
        date = ts_time.strftime('%Y%m%d')
        time = ts_time.strftime('%H%M')
        self.assertEqual(_get_session(number,name,date,time),session)

    def test_get_urls_from_json(self):
        path = os.path.join(settings.BASE_DIR, "../test/data/youtube-playlistitems.json")
        with io.open(path) as f:
            doc = json.load(f)
        urls = _get_urls_from_json(doc)
        self.assertEqual(len(urls),2)
        self.assertEqual(urls[0]['title'],'IETF98 Wrap Up')
        self.assertEqual(urls[0]['url'],'https://www.youtube.com/watch?v=lhYWB5FFkg4&list=PLC86T-6ZTP5jo6kIuqdyeYYhsKv9sUwG1')
        
class RecordingTestCase(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['MEETING_RECORDINGS_DIR']

    def test_page(self):
        meeting = MeetingFactory(type_id='ietf')
        url = reverse('ietf.secr.proceedings.views.recording', kwargs={'meeting_num':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post(self):
        session = SessionFactory(status_id='sched',meeting__type_id='ietf')
        meeting = session.meeting
        group = session.group
        url = reverse('ietf.secr.proceedings.views.recording', kwargs={'meeting_num':meeting.number})
        data = dict(group=group.acronym,external_url='http://youtube.com/xyz',session=session.pk)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,data,follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, group.acronym)
        
        # now test edit
        doc = session.materials.filter(type='recording').first()
        external_url = 'http://youtube.com/aaa'
        url = reverse('ietf.secr.proceedings.views.recording_edit', kwargs={'meeting_num':meeting.number,'name':doc.name})
        response = self.client.post(url,dict(external_url=external_url),follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, external_url)
