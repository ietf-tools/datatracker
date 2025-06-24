# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

import copy
import datetime
import debug  # pyflakes: ignore
import json
import jsonschema
from json import JSONDecodeError
from mock import patch, Mock

from django.http import HttpResponse, JsonResponse
from ietf.meeting.factories import MeetingFactory, RegistrationFactory, RegistrationTicketFactory
from ietf.meeting.models import Registration
from ietf.meeting.utils import (migrate_registrations, get_preferred, process_single_registration,
    get_registration_data, sync_registration_data, fetch_attendance_from_meetings)
from ietf.nomcom.models import Volunteer
from ietf.nomcom.factories import NomComFactory, nomcom_kwargs_for_year
from ietf.person.factories import PersonFactory
from ietf.stats.factories import MeetingRegistrationFactory
from ietf.utils.test_utils import TestCase


class MigrateRegistrationsTests(TestCase):
    def test_new_meeting_registration(self):
        meeting = MeetingFactory(type_id='ietf', number='109')
        reg = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        self.assertEqual(Registration.objects.count(), 0)
        migrate_registrations(initial=True)
        self.assertEqual(Registration.objects.count(), 1)
        new = Registration.objects.first()
        self.assertEqual(new.first_name, reg.first_name)
        self.assertEqual(new.last_name, reg.last_name)
        self.assertEqual(new.email, reg.email)
        self.assertEqual(new.person, reg.person)
        self.assertEqual(new.meeting, meeting)
        self.assertEqual(new.affiliation, reg.affiliation)
        self.assertEqual(new.country_code, reg.country_code)
        self.assertEqual(new.checkedin, reg.checkedin)
        self.assertEqual(new.attended, reg.attended)

    def test_migrate_non_initial(self):
        # with only old meeting
        meeting = MeetingFactory(type_id='ietf', number='109')
        MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        self.assertEqual(Registration.objects.count(), 0)
        migrate_registrations()
        self.assertEqual(Registration.objects.count(), 0)
        # with new meeting
        new_meeting = MeetingFactory(type_id='ietf', number='150')
        new_meeting.date = datetime.date.today() + datetime.timedelta(days=30)
        new_meeting.save()
        MeetingRegistrationFactory(meeting=new_meeting, reg_type='onsite', ticket_type='week_pass')
        migrate_registrations()
        self.assertEqual(Registration.objects.count(), 1)

    def test_updated_meeting_registration(self):
        # setup test initial conditions
        meeting = MeetingFactory(type_id='ietf', number='109')
        reg = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        migrate_registrations(initial=True)
        # change first_name and save
        original = reg.first_name
        reg.first_name = 'NewBob'
        reg.save()
        new = Registration.objects.first()
        self.assertEqual(new.first_name, original)
        migrate_registrations(initial=True)
        new.refresh_from_db()
        self.assertEqual(new.first_name, reg.first_name)

    def test_additional_ticket(self):
        # setup test initial conditions
        meeting = MeetingFactory(type_id='ietf', number='109')
        reg = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        migrate_registrations(initial=True)
        new = Registration.objects.first()
        self.assertEqual(new.tickets.count(), 1)
        # add a second ticket
        reg.reg_type = 'remote'
        reg.pk = None
        reg.save()
        migrate_registrations(initial=True)
        # new.refresh_from_db()
        self.assertEqual(new.tickets.count(), 2)

    def test_cancelled_registration(self):
        # setup test initial conditions
        meeting = MeetingFactory(type_id='ietf', number='109')
        reg = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        migrate_registrations(initial=True)
        reg.delete()
        # do test
        migrate_registrations(initial=True)
        self.assertEqual(Registration.objects.count(), 0)

    def test_get_preferred(self):
        meeting = MeetingFactory(type_id='ietf', number='109')
        onsite = MeetingRegistrationFactory(meeting=meeting, reg_type='onsite', ticket_type='week_pass')
        remote = MeetingRegistrationFactory(meeting=meeting, reg_type='remote', ticket_type='week_pass')
        hackathon = MeetingRegistrationFactory(meeting=meeting, reg_type='hackathon_onsite', ticket_type='week_pass')
        result = get_preferred([remote, onsite, hackathon])
        self.assertEqual(result, onsite)
        result = get_preferred([hackathon, remote])
        self.assertEqual(result, remote)
        result = get_preferred([hackathon])
        self.assertEqual(result, hackathon)


class JsonResponseWithJson(JsonResponse):
    def json(self):
        return json.loads(self.content)


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
