# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug                            # pyflakes:ignore
import io
import json
import os
import shutil

from django.conf import settings
from django.urls import reverse

from ietf.doc.models import Document
from ietf.group.factories import RoleFactory
from ietf.meeting.models import SchedTimeSessAssignment, SchedulingEvent
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.person.models import Person
from ietf.name.models import SessionStatusName
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox

from ietf.secr.proceedings.proc_utils import (import_audio_files,
    get_timeslot_for_filename, normalize_room_name, send_audio_import_warning,
    get_or_create_recording_document, create_recording, get_next_sequence,
    _get_session, _get_urls_from_json)


SECR_USER='secretary'

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
        date = session.official_timeslotassignment().timeslot.time.strftime('%Y%m%d')
        time = session.official_timeslotassignment().timeslot.time.strftime('%H%M')
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
    def setUp(self):
        self.meeting_recordings_dir = self.tempdir('meeting-recordings')
        self.saved_meeting_recordings_dir = settings.MEETING_RECORDINGS_DIR
        settings.MEETING_RECORDINGS_DIR = self.meeting_recordings_dir

    def tearDown(self):
        shutil.rmtree(self.meeting_recordings_dir)
        settings.MEETING_RECORDINGS_DIR = self.saved_meeting_recordings_dir

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
            
    def test_import_audio_files(self):
        session = SessionFactory(status_id='sched',meeting__type_id='ietf')
        meeting = session.meeting
        timeslot = session.official_timeslotassignment().timeslot
        self.create_audio_file_for_timeslot(timeslot)
        import_audio_files(meeting)
        self.assertEqual(session.materials.filter(type='recording').count(),1)

    def create_audio_file_for_timeslot(self, timeslot):
        filename = self.get_filename_for_timeslot(timeslot)
        path = os.path.join(settings.MEETING_RECORDINGS_DIR,'ietf' + timeslot.meeting.number,filename)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with io.open(path, "w") as f:
            f.write('dummy')

    def get_filename_for_timeslot(self, timeslot):
        '''Returns the filename of a session recording given timeslot'''
        return "{prefix}-{room}-{date}.mp3".format(
            prefix=timeslot.meeting.type.slug + timeslot.meeting.number,
            room=normalize_room_name(timeslot.location.name),
            date=timeslot.time.strftime('%Y%m%d-%H%M'))

    def test_import_audio_files_shared_timeslot(self):
        meeting = MeetingFactory(type_id='ietf',number='72')
        mars_session = SessionFactory(meeting=meeting,status_id='sched',group__acronym='mars')
        ames_session = SessionFactory(meeting=meeting,status_id='sched',group__acronym='ames')
        scheduled = SessionStatusName.objects.get(slug='sched')
        SchedulingEvent.objects.create(
            session=mars_session,
            status=scheduled,
            by=Person.objects.get(name='(System)')
        )
        SchedulingEvent.objects.create(
            session=ames_session,
            status=scheduled,
            by=Person.objects.get(name='(System)')
        )
        timeslot = mars_session.official_timeslotassignment().timeslot
        SchedTimeSessAssignment.objects.create(timeslot=timeslot,session=ames_session,schedule=meeting.schedule)
        self.create_audio_file_for_timeslot(timeslot)
        import_audio_files(meeting)
        doc = mars_session.materials.filter(type='recording').first()
        self.assertTrue(doc in ames_session.materials.all())
        self.assertTrue(doc.docalias.filter(name='recording-72-mars-1'))
        self.assertTrue(doc.docalias.filter(name='recording-72-ames-1'))

    def test_normalize_room_name(self):
        self.assertEqual(normalize_room_name('Test Room'),'testroom')
        self.assertEqual(normalize_room_name('Rome/Venice'), 'rome_venice')

    def test_get_timeslot_for_filename(self):
        session = SessionFactory(meeting__type_id='ietf')
        timeslot = session.timeslotassignments.first().timeslot
        name = self.get_filename_for_timeslot(timeslot)
        self.assertEqual(get_timeslot_for_filename(name),timeslot)

    def test_get_or_create_recording_document(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__number=72, group__acronym='mars')
        
        # test create
        filename = 'ietf42-testroom-20000101-0800.mp3'
        docs_before = Document.objects.filter(type='recording').count()
        doc = get_or_create_recording_document(filename,session)
        docs_after = Document.objects.filter(type='recording').count()
        self.assertEqual(docs_after,docs_before + 1)
        self.assertTrue(doc.external_url.endswith(filename))

        # test get
        docs_before = docs_after
        doc2 = get_or_create_recording_document(filename,session)
        docs_after = Document.objects.filter(type='recording').count()
        self.assertEqual(docs_after,docs_before)
        self.assertEqual(doc,doc2)

    def test_create_recording(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__number=72, group__acronym='mars')
        filename = 'ietf42-testroomt-20000101-0800.mp3'
        url = settings.IETF_AUDIO_URL + 'ietf{}/{}'.format(session.meeting.number, filename)
        doc = create_recording(session, url)
        self.assertEqual(doc.name,'recording-72-mars-1')
        self.assertEqual(doc.group,session.group)
        self.assertEqual(doc.external_url,url)
        self.assertTrue(doc in session.materials.all())

    def test_get_next_sequence(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__number=72, group__acronym='mars')
        meeting = session.meeting
        group = session.group
        sequence = get_next_sequence(group,meeting,'recording')
        self.assertEqual(sequence,1)

    def test_send_audio_import_warning(self):
        length_before = len(outbox)
        send_audio_import_warning(['recording-43-badroom-20000101-0800.mp3'])
        self.assertEqual(len(outbox), length_before + 1)
        self.assertTrue('Audio file import' in outbox[-1]['Subject'])
