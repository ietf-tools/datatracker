# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

import copy
import datetime
import debug  # pyflakes: ignore
import json
import jsonschema
from json import JSONDecodeError
from unittest.mock import patch, Mock

from django.http import HttpResponse, JsonResponse
from ietf.meeting.factories import MeetingFactory, RegistrationFactory, RegistrationTicketFactory
from ietf.meeting.models import Registration
from ietf.meeting.utils import (
    process_single_registration,
    get_registration_data, 
    sync_registration_data, 
    fetch_attendance_from_meetings, 
    get_activity_stats
)
from ietf.nomcom.models import Volunteer
from ietf.nomcom.factories import NomComFactory, nomcom_kwargs_for_year
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase
from ietf.meeting.test_data import make_meeting_test_data
from ietf.doc.factories import NewRevisionDocEventFactory, DocEventFactory


class JsonResponseWithJson(JsonResponse):
    def json(self):
        return json.loads(self.content)


class ActivityStatsTests(TestCase):

    def test_activity_stats(self):
        utc = datetime.timezone.utc
        make_meeting_test_data()
        sdate = datetime.date(2016,4,3)
        edate = datetime.date(2016,7,14)
        MeetingFactory(type_id='ietf', date=sdate, number="96")
        MeetingFactory(type_id='ietf', date=edate, number="97")

        NewRevisionDocEventFactory(time=datetime.datetime(2016,4,5,12,0,0,0,tzinfo=utc))
        NewRevisionDocEventFactory(time=datetime.datetime(2016,4,6,12,0,0,0,tzinfo=utc))
        NewRevisionDocEventFactory(time=datetime.datetime(2016,4,7,12,0,0,0,tzinfo=utc))

        NewRevisionDocEventFactory(time=datetime.datetime(2016,6,30,12,0,0,0,tzinfo=utc))
        NewRevisionDocEventFactory(time=datetime.datetime(2016,6,30,13,0,0,0,tzinfo=utc))

        DocEventFactory(doc__std_level_id="ps", doc__type_id="rfc", type="published_rfc", time=datetime.datetime(2016,4,5,12,0,0,0,tzinfo=utc))
        DocEventFactory(doc__std_level_id="bcp", doc__type_id="rfc", type="published_rfc", time=datetime.datetime(2016,4,6,12,0,0,0,tzinfo=utc))
        DocEventFactory(doc__std_level_id="inf", doc__type_id="rfc", type="published_rfc", time=datetime.datetime(2016,4,7,12,0,0,0,tzinfo=utc))
        DocEventFactory(doc__std_level_id="exp", doc__type_id="rfc", type="published_rfc", time=datetime.datetime(2016,4,8,12,0,0,0,tzinfo=utc))

        data = get_activity_stats(sdate, edate)
        self.assertEqual(data['new_drafts_count'], len(data['new_docs']))
        self.assertEqual(data['ffw_new_count'], 2)
        self.assertEqual(data['ffw_new_percent'], '40%')
        rfc_count = 0
        for c in data['counts']:
            rfc_count += data['counts'].get(c)
        self.assertEqual(rfc_count, len(data['rfcs']))


class GetRegistrationsTests(TestCase):

    @patch('ietf.meeting.utils.requests.get')
    def test_get_registation_data(self, mock_get):
        meeting = MeetingFactory(type_id='ietf', number='122')
        person = PersonFactory()
        reg_details = dict(
            first_name=person.first_name(),
            last_name=person.last_name(),
            email=person.email().address,
            affiliation='Microsoft',
            country_code='US',
            meeting=meeting.number,
            checkedin=True,
            is_nomcom_volunteer=False,
            cancelled=False,
            tickets=[{'attendance_type': 'onsite', 'ticket_type': 'week_pass'}],
        )
        reg_data = {'objects': {person.email().address: reg_details}}
        reg_data_bad = copy.deepcopy(reg_data)
        del reg_data_bad['objects'][person.email().address]['email']
        response1 = HttpResponse('Invalid apikey', status=403)
        response2 = JsonResponseWithJson(reg_data)
        response3 = Mock()
        response3.status_code = 200
        response3.json.side_effect = JSONDecodeError("Expecting value", doc="", pos=0)
        response4 = JsonResponseWithJson(reg_data_bad)
        mock_get.side_effect = [response1, response2, response3, response4]
        # test status 403
        with self.assertRaises(Exception):
            get_registration_data(meeting)
        # test status 200 good
        returned_data = get_registration_data(meeting)
        self.assertEqual(returned_data, reg_data)
        # test decode error
        with self.assertRaises(ValueError):
            get_registration_data(meeting)
        # test validation error
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            get_registration_data(meeting)

    @patch('ietf.meeting.utils.get_registration_data')
    def test_sync_registation_data(self, mock_get):
        meeting = MeetingFactory(type_id='ietf', number='122')
        person1 = PersonFactory()
        person2 = PersonFactory()
        items = []
        for person in [person1, person2]:
            items.append(dict(
                first_name=person.first_name(),
                last_name=person.last_name(),
                email=person.email().address,
                affiliation='Microsoft',
                country_code='US',
                meeting=meeting.number,
                checkedin=True,
                is_nomcom_volunteer=False,
                cancelled=False,
                tickets=[{'attendance_type': 'onsite', 'ticket_type': 'week_pass'}],
            ))
        reg_data = {'objects': {items[0]['email']: items[0], items[1]['email']: items[1]}}
        mock_get.return_value = reg_data
        self.assertEqual(Registration.objects.filter(meeting=meeting).count(), 0)
        stats = sync_registration_data(meeting)
        self.assertEqual(Registration.objects.filter(meeting=meeting).count(), 2)
        self.assertEqual(stats['created'], 2)
        # test idempotent
        stats = sync_registration_data(meeting)
        self.assertEqual(Registration.objects.filter(meeting=meeting).count(), 2)
        self.assertEqual(stats['created'], 0)
        # test delete cancelled registration
        del reg_data['objects'][items[1]['email']]
        stats = sync_registration_data(meeting)
        self.assertEqual(Registration.objects.filter(meeting=meeting).count(), 1)
        self.assertEqual(stats['deleted'], 1)

    def test_process_single_registration(self):
        # test new registration
        meeting = MeetingFactory(type_id='ietf', number='122')
        person = PersonFactory()
        reg_data = dict(
            first_name=person.first_name(),
            last_name=person.last_name(),
            email=person.email().address,
            affiliation='Microsoft',
            country_code='US',
            meeting=meeting.number,
            checkedin=True,
            is_nomcom_volunteer=False,
            cancelled=False,
            tickets=[{'attendance_type': 'onsite', 'ticket_type': 'week_pass'}],
        )
        self.assertEqual(meeting.registration_set.count(), 0)
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, 'created')
        self.assertEqual(reg.first_name, person.first_name())
        self.assertEqual(reg.last_name, person.last_name())
        self.assertEqual(reg.email, person.email().address)
        self.assertEqual(reg.affiliation, 'Microsoft')
        self.assertEqual(reg.meeting, meeting)
        self.assertEqual(reg.checkedin, True)
        self.assertEqual(reg.tickets.count(), 1)
        ticket = reg.tickets.first()
        self.assertEqual(ticket.attendance_type.slug, 'onsite')
        self.assertEqual(ticket.ticket_type.slug, 'week_pass')

        # test no change
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, None)

        # test update fields
        reg_data['affiliation'] = 'Cisco'
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, 'updated')
        self.assertEqual(reg.affiliation, 'Cisco')

        # test update tickets
        reg_data['tickets'] = [{'attendance_type': 'remote', 'ticket_type': 'week_pass'}]
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, 'updated')
        self.assertEqual(reg.tickets.count(), 1)
        ticket = reg.tickets.first()
        self.assertEqual(ticket.attendance_type.slug, 'remote')

        # test tickets, two of same
        reg_data['tickets'] = [
            {'attendance_type': 'onsite', 'ticket_type': 'one_day'},
            {'attendance_type': 'onsite', 'ticket_type': 'one_day'},
            {'attendance_type': 'remote', 'ticket_type': 'week_pass'},
        ]
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, 'updated')
        self.assertEqual(reg.tickets.count(), 3)
        self.assertEqual(reg.tickets.filter(attendance_type__slug='onsite', ticket_type__slug='one_day').count(), 2)
        self.assertEqual(reg.tickets.filter(attendance_type__slug='remote', ticket_type__slug='week_pass').count(), 1)

        # test tickets, two of same, delete one
        reg_data['tickets'] = [
            {'attendance_type': 'onsite', 'ticket_type': 'one_day'},
            {'attendance_type': 'remote', 'ticket_type': 'week_pass'},
        ]
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(meeting.registration_set.count(), 1)
        reg = meeting.registration_set.first()
        self.assertEqual(new_reg, reg)
        self.assertEqual(action, 'updated')
        self.assertEqual(reg.tickets.count(), 2)
        self.assertEqual(reg.tickets.filter(attendance_type__slug='onsite', ticket_type__slug='one_day').count(), 1)
        self.assertEqual(reg.tickets.filter(attendance_type__slug='remote', ticket_type__slug='week_pass').count(), 1)

    def test_process_single_registration_nomcom(self):
        '''Test that Volunteer is created if is_nomcom_volunteer=True'''
        meeting = MeetingFactory(type_id='ietf', number='122')
        person = PersonFactory()
        reg_data = dict(
            first_name=person.first_name(),
            last_name=person.last_name(),
            email=person.email().address,
            affiliation='Microsoft',
            country_code='US',
            meeting=meeting.number,
            checkedin=True,
            is_nomcom_volunteer=True,
            cancelled=False,
            tickets=[{'attendance_type': 'onsite', 'ticket_type': 'week_pass'}],
        )
        now = datetime.datetime.now()
        if now.month > 10:
            year = now.year + 1
        else:
            year = now.year
        # create appropriate group and nomcom objects
        nomcom = NomComFactory.create(is_accepting_volunteers=True, **nomcom_kwargs_for_year(year))
        # assert no Volunteers exists
        self.assertEqual(Volunteer.objects.count(), 0)
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual(action, 'created')
        # assert Volunteer exists
        self.assertEqual(Volunteer.objects.count(), 1)
        volunteer = Volunteer.objects.last()
        self.assertEqual(volunteer.person, person)
        self.assertEqual(volunteer.nomcom, nomcom)
        self.assertEqual(volunteer.origin, 'registration')

    def test_process_single_registration_cancelled(self):
        # test cancelled registration, one of two tickets
        meeting = MeetingFactory(type_id='ietf', number='122')
        person = PersonFactory()
        reg = RegistrationFactory(meeting=meeting, person=person, checkedin=False, with_ticket={'attendance_type_id': 'onsite'})
        RegistrationTicketFactory(registration=reg, attendance_type_id='remote', ticket_type_id='week_pass')
        reg_data = dict(
            first_name=person.first_name(),
            last_name=person.last_name(),
            email=person.email().address,
            affiliation='Microsoft',
            country_code='US',
            meeting=meeting.number,
            checkedin=False,
            is_nomcom_volunteer=False,
            cancelled=True,
            tickets=[{'attendance_type': 'onsite', 'ticket_type': 'week_pass'}],
        )
        self.assertEqual(meeting.registration_set.count(), 1)
        self.assertEqual(reg.tickets.count(), 2)
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual((new_reg, action), (None, 'deleted'))
        self.assertEqual(meeting.registration_set.count(), 1)
        self.assertEqual(reg.tickets.count(), 1)
        self.assertTrue(reg.tickets.filter(attendance_type__slug='remote').exists())
        # test cancelled registration, last ticket
        reg_data['tickets'][0]['attendance_type'] = 'remote'
        new_reg, action = process_single_registration(reg_data, meeting)
        self.assertEqual((new_reg, action), (None, 'deleted'))
        self.assertEqual(meeting.registration_set.count(), 0)

    @patch("ietf.meeting.utils.sync_registration_data")
    def test_fetch_attendance_from_meetings(self, mock_sync_reg_data):
        mock_meetings = [object(), object(), object()]
        d1 = dict(created=1, updated=2, deleted=0, processed=3)
        d2 = dict(created=2, updated=2, deleted=0, processed=4)
        d3 = dict(created=1, updated=4, deleted=1, processed=5)
        mock_sync_reg_data.side_effect = (d1, d2, d3)
        stats = fetch_attendance_from_meetings(mock_meetings)
        self.assertEqual(
            [mock_sync_reg_data.call_args_list[n][0][0] for n in range(3)],
            mock_meetings,
        )
        self.assertEqual(stats, [d1, d2, d3])
