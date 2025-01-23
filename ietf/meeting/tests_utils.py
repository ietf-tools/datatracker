# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import debug  # pyflakes: ignore
from ietf.meeting.factories import MeetingFactory # RegistrationFactory, RegistrationTicketFactory
from ietf.meeting.models import Registration
from ietf.meeting.utils import migrate_registrations, get_preferred
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
        hackathon = MeetingRegistrationFactory(meeting=meeting, reg_type='hackathon_onsite', ticket_type='week_pass')
        result = get_preferred([onsite, hackathon])
        self.assertEqual(result, onsite)
