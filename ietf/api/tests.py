# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import sys

from importlib import import_module
from mock import patch

from django.apps import apps
from django.conf import settings
from django.test import Client
from django.urls import reverse as urlreverse
from django.utils import timezone

from tastypie.test import ResourceTestCaseMixin

import debug                            # pyflakes:ignore

from ietf.group.factories import RoleFactory
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.meeting.test_data import make_meeting_test_data
from ietf.person.factories import PersonFactory
from ietf.person.models import PersonalApiKey
from ietf.stats.models import MeetingRegistration
from ietf.utils.mail import outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized

OMITTED_APPS = (
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.ipr',
)

class CustomApiTests(TestCase):

    # Using mock to patch the import functions in ietf.meeting.views, where
    # api_import_recordings() are using them:
    @patch('ietf.meeting.views.import_audio_files')
    def test_notify_meeting_import_audio_files(self, mock_import_audio):
        meeting = make_meeting_test_data()
        client = Client(Accept='application/json')
        # try invalid method GET
        url = urlreverse('ietf.meeting.views.api_import_recordings', kwargs={'number':meeting.number})
        r = client.get(url)
        self.assertEqual(r.status_code, 405)
        # try valid method POST
        r = client.post(url)
        self.assertEqual(r.status_code, 201)

    def test_api_help_page(self):
        url = urlreverse('ietf.api.views.api_help')
        r = self.client.get(url)
        self.assertContains(r, 'The datatracker API', status_code=200)

    def test_api_set_session_video_url(self):
        url = urlreverse('ietf.meeting.views.api_set_session_video_url')
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman')
        recman = recmanrole.person
        meeting = MeetingFactory(type_id='ietf')
        session = SessionFactory(group__type_id='wg', meeting=meeting)
        group = session.group
        apikey = PersonalApiKey.objects.create(endpoint=url, person=recman)
        video = 'https://foo.example.com/bar/beer/'

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole  = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKey.objects.create(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {'apikey': badapikey.hash()} )
        self.assertContains(r, "Restricted to role Recording Manager", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Too long since last regular login", status_code=400)
        recman.user.last_login = timezone.now()
        recman.user.save()

        r = self.client.get(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Method not allowed", status_code=405)

        r = self.client.post(url, {'apikey': apikey.hash()} )
        self.assertContains(r, "Missing meeting parameter", status_code=400)


        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, } )
        self.assertContains(r, "Missing group parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym} )
        self.assertContains(r, "Missing item parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym, 'item': '1'} )
        self.assertContains(r, "Missing url parameter", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': '1', 'group': group.acronym,
                                    'item': '1', 'url': video, })
        self.assertContains(r, "No sessions found for meeting", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': 'bogous',
                                    'item': '1', 'url': video, })
        self.assertContains(r, "No sessions found in meeting '%s' for group 'bogous'"%meeting.number, status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': "foobar", })
        self.assertContains(r, "Invalid url value: 'foobar'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '5', 'url': video, })
        self.assertContains(r, "No item '5' found in list of sessions for group", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': 'foo', 'url': video, })
        self.assertContains(r, "Expected a numeric value for 'item', found 'foo'", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video+'/rum', })
        self.assertContains(r, "Done", status_code=200)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video+'/rum', })
        self.assertContains(r, "URL is the same", status_code=400)

        r = self.client.post(url, {'apikey': apikey.hash(), 'meeting': meeting.number, 'group': group.acronym,
                                    'item': '1', 'url': video, })
        self.assertContains(r, "Done", status_code=200)

        recordings = session.recordings()
        self.assertEqual(len(recordings), 1)
        doc = recordings[0]
        self.assertEqual(doc.external_url, video)
        event = doc.latest_event()
        self.assertEqual(event.by, recman)

    def test_person_export(self):
        person = PersonFactory()
        url = urlreverse('ietf.api.views.PersonalInformationExportView')
        login_testing_unauthorized(self, person.user.username, url)
        r = self.client.get(url)
        jsondata = r.json()
        data = jsondata['person.person'][str(person.id)]
        self.assertEqual(data['name'], person.name)
        self.assertEqual(data['ascii'], person.ascii)
        self.assertEqual(data['user']['email'], person.user.email)

    def test_api_v2_person_export_view(self):
        url = urlreverse('ietf.api.views.ApiV2PersonExportView')
        secretariat_role = RoleFactory(group__acronym='secretariat', name_id='secr')
        secretariat = secretariat_role.person
        apikey = PersonalApiKey.objects.create(endpoint=url, person=secretariat)

        # error cases
        r = self.client.post(url, {})
        self.assertContains(r, "Missing apikey parameter", status_code=400)

        badrole = RoleFactory(group__type_id='ietf', name_id='ad')
        badapikey = PersonalApiKey.objects.create(endpoint=url, person=badrole.person)
        badrole.person.user.last_login = timezone.now()
        badrole.person.user.save()
        r = self.client.post(url, {'apikey': badapikey.hash()})
        self.assertContains(r, "Restricted to role Secretariat", status_code=403)

        r = self.client.post(url, {'apikey': apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        secretariat.user.last_login = timezone.now()
        secretariat.user.save()

        r = self.client.post(url, {'apikey': apikey.hash()})
        self.assertContains(r, "No filters provided", status_code=400)

        # working case
        r = self.client.post(url, {'apikey': apikey.hash(), 'email': secretariat.email().address, '_expand': 'user'})
        self.assertEqual(r.status_code, 200)
        jsondata = r.json()
        data = jsondata['person.person'][str(secretariat.id)]
        self.assertEqual(data['name'], secretariat.name)
        self.assertEqual(data['ascii'], secretariat.ascii)
        self.assertEqual(data['user']['email'], secretariat.user.email)


    def test_api_v2_person_access_meetecho(self):
        url = urlreverse('ietf.api.views.person_access_meetecho')
        person = PersonFactory()
        apikey = PersonalApiKey.objects.create(endpoint=url, person=person)

        # error cases
        r = self.client.get(url, {'apikey': apikey.hash()})
        self.assertContains(r, "Too long since last regular login", status_code=400)
        person.user.last_login = timezone.now()
        person.user.save()

        # working case
        r = self.client.get(url, {'apikey': apikey.hash()})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['name'], person.name)
        self.assertEqual(data['email'], person.email().address)

    def test_api_new_meeting_registration(self):
        meeting = MeetingFactory(type_id='ietf')
        reg = {
                'apikey': 'invalid',
                'affiliation': "Alguma Corporação",
                'country_code': 'PT',
                'email': 'foo@example.pt',
                'first_name': 'Foo',
                'last_name': 'Bar',
                'meeting': meeting.number,
                'reg_type': 'hackathon',
                'ticket_type': 'regular',
            }
        url = urlreverse('ietf.api.views.api_new_meeting_registration')
        r = self.client.post(url, reg)
        self.assertContains(r, 'Invalid apikey', status_code=400)
        oidcp = PersonFactory(user__is_staff=True)
        # Make sure 'oidcp' has an acceptable role
        RoleFactory(name_id='robot', person=oidcp, email=oidcp.email(), group__acronym='secretariat')
        key  = PersonalApiKey.objects.create(person=oidcp, endpoint=url)
        reg['apikey'] = key.hash()
        #
        # Test valid POST
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration, Email sent", status_code=202)
        #
        # Check outgoing mail
        self.assertEqual(len(outbox), 1)
        body = get_payload_text(outbox[-1])
        self.assertIn(reg['email'], outbox[-1]['To'] )
        self.assertIn(reg['email'], body)
        self.assertIn('account creation request', body)
        #
        # Check record
        obj = MeetingRegistration.objects.get(email=reg['email'], meeting__number=reg['meeting'])
        for key in [ 'affiliation', 'country_code', 'first_name', 'last_name', 'person', 'reg_type', 'ticket_type', ]:
            self.assertEqual(getattr(obj, key), reg.get(key), "Bad data for field '%s'" % key)
        #
        # Test with existing user
        person = PersonFactory()
        reg['email'] = person.email().address
        reg['first_name'] = person.first_name()
        reg['last_name'] = person.last_name()
        #
        r = self.client.post(url, reg)
        self.assertContains(r, "Accepted, New registration", status_code=202)
        #
        # There should be no new outgoing mail
        self.assertEqual(len(outbox), 1)
        # Test incomplete POST
        drop_fields = ['affiliation', 'first_name', 'reg_type']
        for field in drop_fields:
            del reg[field]
        r = self.client.post(url, reg)        
        self.assertContains(r, 'Missing parameters:', status_code=400)
        err, fields = r.content.decode().split(':', 1)
        missing_fields = [ f.strip() for f in fields.split(',') ]
        self.assertEqual(set(missing_fields), set(drop_fields))

class TastypieApiTestCase(ResourceTestCaseMixin, TestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app_name
        super(TastypieApiTestCase, self).__init__(*args, **kwargs)

    def test_api_top_level(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1/")
        self.assertValidJSONResponse(r)        
        resource_list = r.json()

        for name in self.apps:
            if not name in self.apps:
                sys.stderr.write("Expected a REST API resource for %s, but didn't find one\n" % name)

        for name in self.apps:
            self.assertIn(name, resource_list,
                        "Expected a REST API resource for %s, but didn't find one" % name)

    def test_all_model_resources_exist(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1")
        top = r.json()
        for name in self.apps:
            app_name = self.apps[name]
            app = import_module(app_name)
            self.assertEqual("/api/v1/%s/"%name, top[name]["list_endpoint"])
            r = client.get(top[name]["list_endpoint"])
            self.assertValidJSONResponse(r)
            app_resources = r.json()
            #
            model_list = apps.get_app_config(name).get_models()
            for model in model_list:
                if not model._meta.model_name in list(app_resources.keys()):
                    #print("There doesn't seem to be any resource for model %s.models.%s"%(app.__name__,model.__name__,))
                    self.assertIn(model._meta.model_name, list(app_resources.keys()),
                        "There doesn't seem to be any API resource for model %s.models.%s"%(app.__name__,model.__name__,))

