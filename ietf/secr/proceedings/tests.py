import debug                            # pyflakes:ignore
import json
import os
import shutil
from apiclient.discovery import build
from apiclient.http import HttpMock
from mock import patch

from django.conf import settings
from django.urls import reverse

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.models import Session, TimeSlot, SchedTimeSessAssignment
from ietf.meeting.test_data import make_meeting_test_data
from ietf.name.models import SessionStatusName
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox

from ietf.secr.proceedings.proc_utils import (import_audio_files,
    get_timeslot_for_filename, normalize_room_name, send_audio_import_warning,
    get_or_create_recording_document, create_recording, get_next_sequence,
    get_youtube_playlistid, get_youtube_videos, import_youtube_video_urls,
    _get_session, _get_urls_from_json)


SECR_USER='secretary'

class ProceedingsTestCase(TestCase):
    def test_main(self):
        "Main Test"
        make_test_data()
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
    @patch('ietf.secr.proceedings.proc_utils.get_youtube_videos')
    @patch('ietf.secr.proceedings.proc_utils.get_youtube_playlistid')
    def test_import_youtube_video_urls(self, mock_playlistid, mock_videos):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym='mars').first()
        title = self._get_video_title_for_session(session)
        url = 'https://youtube.com?v=test'
        mock_playlistid.return_value = 'PLC86T-6ZTP5g87jdxNqdWV5475U-yEE8M'
        mock_videos.return_value = [{'title':title,'url':url}]
        discovery = os.path.join(settings.BASE_DIR, "../test/data/youtube-discovery.json")
        http = HttpMock(discovery, {'status': '200'})
        import_youtube_video_urls(meeting=meeting, http=http)
        doc = Document.objects.get(external_url=url)
        self.assertTrue(doc in session.materials.all())

    def _get_video_title_for_session(self, session):
        '''Returns the youtube video title of a session recording given session'''
        timeslot = session.official_timeslotassignment().timeslot
        return "{prefix}-{group}-{date}".format(
            prefix=session.meeting.type.slug + session.meeting.number,
            group=session.group.acronym,
            date=timeslot.time.strftime('%Y%m%d-%H%M')).upper()

    def test_get_youtube_playlistid(self):
        discovery = os.path.join(settings.BASE_DIR, "../test/data/youtube-discovery.json")
        http = HttpMock(discovery, {'status': '200'})
        youtube = build(settings.YOUTUBE_API_SERVICE_NAME, settings.YOUTUBE_API_VERSION,
            developerKey='',http=http)
        path = os.path.join(settings.BASE_DIR, "../test/data/youtube-playlistid.json")
        http = HttpMock(path, {'status': '200'})
        self.assertEqual(get_youtube_playlistid(youtube, 'IETF98', http=http),'PLC86T-test')
  
    def test_get_youtube_videos(self):
        discovery = os.path.join(settings.BASE_DIR, "../test/data/youtube-discovery.json")
        http = HttpMock(discovery, {'status': '200'})
        youtube = build(settings.YOUTUBE_API_SERVICE_NAME, settings.YOUTUBE_API_VERSION,
            developerKey='',http=http)
        path = os.path.join(settings.BASE_DIR, "../test/data/youtube-playlistitems.json")
        http = HttpMock(path, {'status': '200'})
        videos = get_youtube_videos(youtube, 'PLC86T', http=http)
        self.assertEqual(len(videos),2)

    def test_get_session(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym='mars').first()
        number = meeting.number
        name = session.group.acronym
        date = session.official_timeslotassignment().timeslot.time.strftime('%Y%m%d')
        time = session.official_timeslotassignment().timeslot.time.strftime('%H%M')
        self.assertEqual(_get_session(number,name,date,time),session)

    def test_get_urls_from_json(self):
        path = os.path.join(settings.BASE_DIR, "../test/data/youtube-playlistitems.json")
        with open(path) as f:
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
        meeting = make_meeting_test_data()
        url = reverse('ietf.secr.proceedings.views.recording', kwargs={'meeting_num':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post(self):
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        session = Session.objects.filter(meeting=meeting,group=group).first()
        # explicitly set to scheduled for this test
        status = SessionStatusName.objects.get(slug='sched')
        session.status = status
        session.save()
        url = reverse('ietf.secr.proceedings.views.recording', kwargs={'meeting_num':meeting.number})
        data = dict(group=group.acronym,external_url='http://youtube.com/xyz',session=session.pk)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,data,follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(group.acronym in response.content)
        
        # now test edit
        doc = session.materials.filter(type='recording').first()
        external_url = 'http://youtube.com/aaa'
        url = reverse('ietf.secr.proceedings.views.recording_edit', kwargs={'meeting_num':meeting.number,'name':doc.name})
        response = self.client.post(url,dict(external_url=external_url),follow=True)
        self.assertEqual(response.status_code, 200)
        self.failUnless(external_url in response.content)
            
    def test_import_audio_files(self):
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        session = Session.objects.filter(meeting=meeting,group=group).first()
        status = SessionStatusName.objects.get(slug='sched')
        session.status = status
        session.save()
        timeslot = session.official_timeslotassignment().timeslot
        self.create_audio_file_for_timeslot(timeslot)
        import_audio_files(meeting)
        self.assertEqual(session.materials.filter(type='recording').count(),1)

    def create_audio_file_for_timeslot(self, timeslot):
        filename = self.get_filename_for_timeslot(timeslot)
        path = os.path.join(settings.MEETING_RECORDINGS_DIR,'ietf' + timeslot.meeting.number,filename)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write('dummy')

    def get_filename_for_timeslot(self, timeslot):
        '''Returns the filename of a session recording given timeslot'''
        return "{prefix}-{room}-{date}.mp3".format(
            prefix=timeslot.meeting.type.slug + timeslot.meeting.number,
            room=normalize_room_name(timeslot.location.name),
            date=timeslot.time.strftime('%Y%m%d-%H%M'))

    def test_import_audio_files_shared_timeslot(self):
        meeting = make_meeting_test_data()
        mars_session = Session.objects.filter(meeting=meeting,group__acronym='mars').first()
        ames_session = Session.objects.filter(meeting=meeting,group__acronym='ames').first()
        scheduled = SessionStatusName.objects.get(slug='sched')
        mars_session.status = scheduled
        mars_session.save()
        ames_session.status = scheduled
        ames_session.save()
        timeslot = mars_session.official_timeslotassignment().timeslot
        SchedTimeSessAssignment.objects.create(timeslot=timeslot,session=ames_session,schedule=meeting.agenda)
        self.create_audio_file_for_timeslot(timeslot)
        import_audio_files(meeting)
        doc = mars_session.materials.filter(type='recording').first()
        self.assertTrue(doc in ames_session.materials.all())
        self.assertTrue(doc.docalias_set.filter(name='recording-42-mars-1'))
        self.assertTrue(doc.docalias_set.filter(name='recording-42-ames-1'))

    def test_normalize_room_name(self):
        self.assertEqual(normalize_room_name('Test Room'),'testroom')
        self.assertEqual(normalize_room_name('Rome/Venice'), 'rome_venice')

    def test_get_timeslot_for_filename(self):
        meeting = make_meeting_test_data()
        timeslot = TimeSlot.objects.filter(meeting=meeting,type='session').first()
        name = self.get_filename_for_timeslot(timeslot)
        self.assertEqual(get_timeslot_for_filename(name),timeslot)

    def test_get_or_create_recording_document(self):
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        session = Session.objects.filter(meeting=meeting,group=group).first()
        
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
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        session = Session.objects.filter(meeting=meeting,group=group).first()
        filename = 'ietf42-testroomt-20000101-0800.mp3'
        url = settings.IETF_AUDIO_URL + 'ietf{}/{}'.format(meeting.number, filename)
        doc = create_recording(session, url)
        self.assertEqual(doc.name,'recording-42-mars-1')
        self.assertEqual(doc.group,group)
        self.assertEqual(doc.external_url,url)
        self.assertTrue(doc in session.materials.all())

    def test_get_next_sequence(self):
        meeting = make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        sequence = get_next_sequence(group,meeting,'recording')
        self.assertEqual(sequence,1)

    def test_send_audio_import_warning(self):
        length_before = len(outbox)
        send_audio_import_warning(['recording-43-badroom-20000101-0800.mp3'])
        self.assertEqual(len(outbox), length_before + 1)
        self.assertTrue('Audio file import' in outbox[-1]['Subject'])
