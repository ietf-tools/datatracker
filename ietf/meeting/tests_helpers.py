# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-
from unittest.mock import patch, Mock

from django.conf import settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import override_settings, RequestFactory

from ietf.group.factories import GroupFactory
from ietf.group.models import Group
from ietf.meeting.factories import SessionFactory, MeetingFactory, TimeSlotFactory
from ietf.meeting.helpers import (AgendaFilterOrganizer, AgendaKeywordTagger,
    delete_interim_session_conferences, sessions_post_save, sessions_post_cancel,
    create_interim_session_conferences)
from ietf.meeting.models import SchedTimeSessAssignment, Session
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.meetecho import Conference
from ietf.utils.test_utils import TestCase


# override the legacy office hours setting to guarantee consistency with the tests
@override_settings(MEETING_LEGACY_OFFICE_HOURS_END=111)
class AgendaKeywordTaggerTests(TestCase):
    def do_test_tag_assignments_with_filter_keywords(self, meeting_num, bof=False, historic=None):
        """Assignments should be tagged properly
        
        The historic param can be None, group, or parent, to specify whether to test
        with no historic_group, a historic_group but no historic_parent, or both.
        """
        # decide whether meeting should use legacy keywords (for office hours)
        legacy_keywords = meeting_num <= 111

        # create meeting and groups
        meeting = MeetingFactory(type_id='ietf', number=meeting_num)
        group_state_id = 'bof' if bof else 'active'
        group = GroupFactory(state_id=group_state_id)

        # Set up the historic group and parent if needed. Keep track of these as expected_*
        # for later reference. If not using historic group or parent, fall back to the non-historic
        # groups.
        if historic:
            expected_group = GroupFactory(state_id=group_state_id)
            if historic == 'parent':
                expected_area = GroupFactory(type_id='area')
                expected_group.historic_parent = expected_area
            else:
                expected_area = expected_group.parent
        else:
            expected_group = group
            expected_area = group.parent

        # create sessions, etc
        session_data = [
            {
                'description': 'regular wg session',
                'session': SessionFactory(
                    group=group, meeting=meeting, add_to_schedule=False,
                    purpose_id='none' if legacy_keywords else 'regular',
                    type_id='regular',
                ),
                'expected_keywords': {
                    expected_group.acronym,
                    expected_area.acronym,
                    # if legacy_keywords, next line repeats a previous entry to avoid adding anything to the set
                    expected_group.acronym if legacy_keywords else 'regular',
                    f'{expected_group.acronym}-sessa',
                },
            },
            {
                'description': 'plenary session',
                'session': SessionFactory(
                    group=group, meeting=meeting, add_to_schedule=False,
                    name=f'{group.acronym} plenary',
                    purpose_id='none' if legacy_keywords else 'plenary',
                    type_id='plenary',
                ),
                'expected_keywords': {
                    expected_group.acronym,
                    expected_area.acronym,
                    f'{expected_group.acronym}-sessb',
                    'plenary',
                    f'{group.acronym}-plenary',
                },
            },
            {
                'description': 'office hours session',
                'session': SessionFactory(
                    group=group, meeting=meeting, add_to_schedule=False,
                    name=f'{group.acronym} office hours',
                    purpose_id='none' if legacy_keywords else 'officehours',
                    type_id='other',
                ),
                'expected_keywords': {
                    expected_group.acronym,
                    expected_area.acronym,
                    f'{expected_group.acronym}-sessc',
                    'officehours',
                    f'{group.acronym}-officehours' if legacy_keywords else 'officehours',
                    # officehours in prev line is a repeated value - since this is a set, it will be ignored
                    f'{group.acronym}-office-hours',
                },
            }
        ]
        for sd in session_data:
            sd['session'].timeslotassignments.create(
                timeslot=TimeSlotFactory(meeting=meeting, type=sd['session'].type),
                schedule=meeting.schedule,
            )

        assignments = meeting.schedule.assignments.all()

        # Set up historic groups if needed.
        if historic:
            for a in assignments:
                a.session.historic_group = expected_group

        # Execute the method under test
        AgendaKeywordTagger(assignments=assignments).apply()

        # Assert expected results

        # check the assignment count - paranoid, but the method mutates its input so let's be careful
        self.assertEqual(len(assignments), len(session_data), 'Should not change number of assignments')

        assignment_by_session_pk = {a.session.pk: a for a in assignments}
        for sd in session_data:
            assignment = assignment_by_session_pk[sd['session'].pk]
            expected_filter_keywords = sd['expected_keywords']
            if bof:
                expected_filter_keywords.add('bof')
            self.assertCountEqual(
                assignment.filter_keywords,
                expected_filter_keywords,
                f'Assignment for "{sd["description"]}" has incorrect filter keywords'
            )

    @override_settings(MEETING_LEGACY_OFFICE_HOURS_END=111)
    def test_tag_assignments_with_filter_keywords(self):
        # use distinct meeting numbers > 111 for non-legacy keyword tests
        self.do_test_tag_assignments_with_filter_keywords(112)
        self.do_test_tag_assignments_with_filter_keywords(113, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(114, historic='parent')
        self.do_test_tag_assignments_with_filter_keywords(115, bof=True)
        self.do_test_tag_assignments_with_filter_keywords(116, bof=True, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(117, bof=True, historic='parent')


    @override_settings(MEETING_LEGACY_OFFICE_HOURS_END=111)
    def test_tag_assignments_with_filter_keywords_legacy(self):
        # use distinct meeting numbers <= 111 for legacy keyword tests
        self.do_test_tag_assignments_with_filter_keywords(101)
        self.do_test_tag_assignments_with_filter_keywords(102, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(103, historic='parent')
        self.do_test_tag_assignments_with_filter_keywords(104, bof=True)
        self.do_test_tag_assignments_with_filter_keywords(105, bof=True, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(106, bof=True, historic='parent')


class AgendaFilterOrganizerTests(TestCase):
    def test_get_filter_categories(self):
        self.do_get_filter_categories_test(False)

    def test_get_legacy_filter_categories(self):
        self.do_get_filter_categories_test(True)

    def do_get_filter_categories_test(self, legacy):
        # set up
        meeting = make_meeting_test_data()
        if legacy:
            meeting.session_set.all().update(purpose_id='none')  # legacy meetings did not have purposes
        else:
            meeting.number = str(settings.MEETING_LEGACY_OFFICE_HOURS_END + 1)
            meeting.save()

        # create extra groups for testing
        iab = Group.objects.get(acronym='iab')
        iab_child = GroupFactory(type_id='iab', parent=iab)
        irtf = Group.objects.get(acronym='irtf')
        irtf_child = GroupFactory(parent=irtf, state_id='bof')

        # non-area group sessions
        SessionFactory(group=iab_child, meeting=meeting)
        SessionFactory(group=irtf_child, meeting=meeting)

        # office hours session
        SessionFactory(
            group=Group.objects.get(acronym='farfut'),
            purpose_id='officehours' if not legacy else 'none',
            type_id='other',
            name='FARFUT office hours',
            meeting=meeting
        )

        if legacy:
            expected = [
                [
                    # area category
                    {'label': 'FARFUT', 'keyword': 'farfut', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'ames', 'keyword': 'ames', 'is_bof': False, 'toggled_by': ['farfut']},
                         {'label': 'mars', 'keyword': 'mars', 'is_bof': False, 'toggled_by': ['farfut']},
                     ]},
                ],
                [
                    # non-area category
                    {'label': 'IAB', 'keyword': 'iab', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': iab_child.acronym, 'keyword': iab_child.acronym, 'is_bof': False, 'toggled_by': ['iab']},
                     ]},
                    {'label': 'IRTF', 'keyword': 'irtf', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': irtf_child.acronym, 'keyword': irtf_child.acronym, 'is_bof': True, 'toggled_by': ['bof', 'irtf']},
                     ]},
                ],
                [
                    # non-group category
                    {'label': 'Office Hours', 'keyword': 'officehours', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'FARFUT', 'keyword': 'farfut-officehours', 'is_bof': False, 'toggled_by': ['officehours', 'farfut']}
                     ]},
                    {'label': None, 'keyword': None,'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'BoF', 'keyword': 'bof', 'is_bof': False, 'toggled_by': []},
                         {'label': 'Plenary', 'keyword': 'plenary', 'is_bof': False, 'toggled_by': []},
                     ]},
                ],
            ]
        else:
            expected = [
                [
                    # area category
                    {'label': 'FARFUT', 'keyword': 'farfut', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'ames', 'keyword': 'ames', 'is_bof': False, 'toggled_by': ['farfut']},
                         {'label': 'mars', 'keyword': 'mars', 'is_bof': False, 'toggled_by': ['farfut']},
                     ]},
                ],
                [
                    # non-area category
                    {'label': 'IAB', 'keyword': 'iab', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': iab_child.acronym, 'keyword': iab_child.acronym, 'is_bof': False, 'toggled_by': ['iab']},
                     ]},
                    {'label': 'IRTF', 'keyword': 'irtf', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': irtf_child.acronym, 'keyword': irtf_child.acronym, 'is_bof': True, 'toggled_by': ['bof', 'irtf']},
                     ]},
                ],
                [
                    # non-group category
                    {'label': 'Administrative', 'keyword': 'admin', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'Registration', 'keyword': 'registration', 'is_bof': False, 'toggled_by': ['admin', 'secretariat']},
                     ]},
                    {'label': 'Closed meeting', 'keyword': 'closed_meeting', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'IESG Breakfast', 'keyword': 'iesg-breakfast', 'is_bof': False, 'toggled_by': ['closed_meeting', 'iesg']},
                     ]},
                    {'label': 'Office hours', 'keyword': 'officehours', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'FARFUT office hours', 'keyword': 'farfut-office-hours', 'is_bof': False, 'toggled_by': ['officehours', 'farfut']}
                     ]},
                    {'label': 'Plenary', 'keyword': 'plenary', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'IETF Plenary', 'keyword': 'ietf-plenary', 'is_bof': False, 'toggled_by': ['plenary', 'ietf']},
                     ]},
                    {'label': 'Social', 'keyword': 'social', 'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'Morning Break', 'keyword': 'morning-break', 'is_bof': False, 'toggled_by': ['social', 'secretariat']},
                     ]},
                    {'label': None, 'keyword': None,'is_bof': False, 'toggled_by': [],
                     'children': [
                         {'label': 'BoF', 'keyword': 'bof', 'is_bof': False, 'toggled_by': []},
                     ]},
                ],
            ]
        # put all the above together for single-column tests
        expected_single_category = [sum(expected, [])]

        ###
        # test using sessions
        sessions = meeting.session_set.all()
        AgendaKeywordTagger(sessions=sessions).apply()

        # default
        filter_organizer = AgendaFilterOrganizer(sessions=sessions)
        self.assertEqual(filter_organizer.get_filter_categories(), expected)

        # single-column
        filter_organizer = AgendaFilterOrganizer(sessions=sessions, single_category=True)
        self.assertEqual(filter_organizer.get_filter_categories(), expected_single_category)

        ###
        # test again using assignments
        assignments = SchedTimeSessAssignment.objects.filter(
            schedule__in=(meeting.schedule, meeting.schedule.base)
        )
        AgendaKeywordTagger(assignments=assignments).apply()

        # default
        filter_organizer = AgendaFilterOrganizer(assignments=assignments)
        self.assertEqual(filter_organizer.get_filter_categories(), expected)

        # single-column
        filter_organizer = AgendaFilterOrganizer(assignments=assignments, single_category=True)
        self.assertEqual(filter_organizer.get_filter_categories(), expected_single_category)

    def test_get_non_area_keywords(self):
        # set up
        meeting = make_meeting_test_data()

        # create a session in a 'special' group, which should then appear in the non-area keywords
        team = GroupFactory(type_id='team')
        SessionFactory(group=team, meeting=meeting)

        # and a BoF
        bof = GroupFactory(state_id='bof')
        SessionFactory(group=bof, meeting=meeting)

        expected = sorted(['bof', 'plenary', team.acronym.lower()])

        ###
        # by sessions
        sessions = meeting.session_set.all()
        AgendaKeywordTagger(sessions=sessions).apply()
        filter_organizer = AgendaFilterOrganizer(sessions=sessions)
        self.assertEqual(filter_organizer.get_non_area_keywords(), expected)

        filter_organizer = AgendaFilterOrganizer(sessions=sessions, single_category=True)
        self.assertEqual(filter_organizer.get_non_area_keywords(), expected)

        ###
        # by assignments
        assignments = meeting.schedule.assignments.all()
        AgendaKeywordTagger(assignments=assignments).apply()
        filter_organizer = AgendaFilterOrganizer(assignments=assignments)
        self.assertEqual(filter_organizer.get_non_area_keywords(), expected)

        filter_organizer = AgendaFilterOrganizer(assignments=assignments, single_category=True)
        self.assertEqual(filter_organizer.get_non_area_keywords(), expected)


@override_settings(
    MEETECHO_API_CONFIG={
        'api_base': 'https://example.com',
        'client_id': 'datatracker',
        'client_secret': 'secret',
        'request_timeout': 3.01,
    }
)
class InterimTests(TestCase):
    @patch('ietf.utils.meetecho.ConferenceManager')
    def test_delete_interim_session_conferences(self, mock):
        mock_conf_mgr = mock.return_value  # "instance" seen by the internals
        sessions = [
            SessionFactory(meeting__type_id='interim', remote_instructions='fake-meetecho-url'),
            SessionFactory(meeting__type_id='interim', remote_instructions='other-fake-meetecho-url'),
        ]
        timeslots = [
            session.official_timeslotassignment().timeslot for session in sessions
        ]
        conferences = [
            Conference(
                manager=mock_conf_mgr, id=1, public_id='some-uuid', description='desc',
                start_time=timeslots[0].time, duration=timeslots[0].duration, url='fake-meetecho-url',
                deletion_token='please-delete-me',
            ),
            Conference(
                manager=mock_conf_mgr, id=2, public_id='some-uuid-2', description='desc',
                start_time=timeslots[1].time, duration=timeslots[1].duration, url='other-fake-meetecho-url',
                deletion_token='please-delete-me-as-well',
            ),
        ]

        # should not call the API if MEETECHO_API_CONFIG is not defined
        with override_settings():  # will undo any changes to settings in the block
            del settings.MEETECHO_API_CONFIG
            delete_interim_session_conferences([sessions[0], sessions[1]])
        self.assertFalse(mock.called)

        # no conferences, no sessions being deleted -> no conferences deleted
        mock.reset_mock()
        mock_conf_mgr.fetch.return_value = []
        delete_interim_session_conferences([])
        self.assertFalse(mock_conf_mgr.delete_conference.called)

        # two conferences, no sessions being deleted -> no conferences deleted
        mock_conf_mgr.fetch.return_value = [conferences[0], conferences[1]]
        mock_conf_mgr.delete_conference.reset_mock()
        delete_interim_session_conferences([])
        self.assertFalse(mock_conf_mgr.delete_conference.called)
        mock_conf_mgr.delete_conference.reset_mock()

        # one conference, other session being deleted -> no conferences deleted
        mock_conf_mgr.fetch.return_value = [conferences[0]]
        delete_interim_session_conferences([sessions[1]])
        self.assertFalse(mock_conf_mgr.delete_conference.called)

        # one conference, same session being deleted -> conference deleted
        mock.reset_mock()
        mock_conf_mgr.fetch.return_value = [conferences[0]]
        delete_interim_session_conferences([sessions[0]])
        self.assertTrue(mock_conf_mgr.delete_conference.called)
        self.assertCountEqual(
            mock_conf_mgr.delete_conference.call_args[0],
            (conferences[0],)
        )

        # two conferences, one being deleted -> correct conference deleted
        mock.reset_mock()
        mock_conf_mgr.fetch.return_value = [conferences[0], conferences[1]]
        delete_interim_session_conferences([sessions[1]])
        self.assertTrue(mock_conf_mgr.delete_conference.called)
        self.assertEqual(mock_conf_mgr.delete_conference.call_count, 1)
        self.assertEqual(
            mock_conf_mgr.delete_conference.call_args[0],
            (conferences[1],)
        )

        # two conferences, both being deleted -> both conferences deleted
        mock.reset_mock()
        mock_conf_mgr.fetch.return_value = [conferences[0], conferences[1]]
        delete_interim_session_conferences([sessions[0], sessions[1]])
        self.assertTrue(mock_conf_mgr.delete_conference.called)
        self.assertEqual(mock_conf_mgr.delete_conference.call_count, 2)
        args_list = [call_args[0] for call_args in mock_conf_mgr.delete_conference.call_args_list]
        self.assertCountEqual(
            args_list,
            ((conferences[0],), (conferences[1],)),
        )

    @patch('ietf.meeting.helpers.delete_interim_session_conferences')
    def test_sessions_post_cancel(self, mock):
        sessions_post_cancel(RequestFactory().post('/some/url'), 'sessions arg')
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_args[0], ('sessions arg',))

    @patch('ietf.meeting.helpers.delete_interim_session_conferences')
    def test_sessions_post_cancel_delete_exception(self, mock):
        """sessions_post_cancel prevents exceptions percolating up"""
        mock.side_effect = RuntimeError('oops')
        sessions = SessionFactory.create_batch(3, meeting__type_id='interim')
        # create mock request with session / message storage
        request = RequestFactory().post('/some/url')
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        sessions_post_cancel(request, sessions)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_args[0], (sessions,))
        msgs = [str(msg) for msg in messages]
        self.assertEqual(len(msgs), 1)
        self.assertIn('An error occurred', msgs[0])

    @patch('ietf.utils.meetecho.ConferenceManager')
    def test_create_interim_session_conferences(self, mock):
        mock_conf_mgr = mock.return_value  # "instance" seen by the internals
        sessions = [
            SessionFactory(meeting__type_id='interim', remote_instructions='junk'),
            SessionFactory(meeting__type_id='interim', remote_instructions=''),
        ]
        timeslots = [
            session.official_timeslotassignment().timeslot for session in sessions
        ]

        with override_settings():  # will undo any changes to settings in the block
            del settings.MEETECHO_API_CONFIG
            create_interim_session_conferences([sessions[0], sessions[1]])
        self.assertFalse(mock.called)

        # create for 0 sessions
        mock.reset_mock()
        create_interim_session_conferences([])
        self.assertFalse(mock_conf_mgr.create.called)
        self.assertEqual(
            Session.objects.get(pk=sessions[0].pk).remote_instructions,
            'junk',
        )

        # create for 1 session
        mock.reset_mock()
        mock_conf_mgr.create.return_value = [
            Conference(
                manager=mock_conf_mgr, id=1, public_id='some-uuid', description='desc',
                start_time=timeslots[0].time, duration=timeslots[0].duration, url='fake-meetecho-url',
                deletion_token='please-delete-me',
            ),
        ]
        create_interim_session_conferences([sessions[0]])
        self.assertTrue(mock_conf_mgr.create.called)
        self.assertCountEqual(
            mock_conf_mgr.create.call_args[1],
            {
                'group': sessions[0].group,
                'description': str(sessions[0]),
                'start_time': timeslots[0].time,
                'duration': timeslots[0].duration,
            }
        )
        self.assertEqual(
            Session.objects.get(pk=sessions[0].pk).remote_instructions,
            'fake-meetecho-url',
        )

        # create for 2 sessions
        mock.reset_mock()
        mock_conf_mgr.create.side_effect = [
            [Conference(
                manager=mock_conf_mgr, id=1, public_id='some-uuid', description='desc',
                start_time=timeslots[0].time, duration=timeslots[0].duration, url='different-fake-meetecho-url',
                deletion_token='please-delete-me',
            )],
            [Conference(
                manager=mock_conf_mgr, id=2, public_id='another-uuid', description='desc',
                start_time=timeslots[1].time, duration=timeslots[1].duration, url='another-fake-meetecho-url',
                deletion_token='please-delete-me-too',
            )],
        ]
        create_interim_session_conferences([sessions[0], sessions[1]])
        self.assertTrue(mock_conf_mgr.create.called)
        self.assertCountEqual(
            mock_conf_mgr.create.call_args_list,
            [
                ({
                    'group': sessions[0].group,
                    'description': str(sessions[0]),
                    'start_time': timeslots[0].time,
                    'duration': timeslots[0].duration,
                 },),
                ({
                    'group': sessions[1].group,
                    'description': str(sessions[1]),
                    'start_time': timeslots[1].time,
                    'duration': timeslots[1].duration,
                 },),
            ]
        )
        self.assertEqual(
            Session.objects.get(pk=sessions[0].pk).remote_instructions,
            'different-fake-meetecho-url',
        )
        self.assertEqual(
            Session.objects.get(pk=sessions[1].pk).remote_instructions,
            'another-fake-meetecho-url',
        )

    @patch('ietf.utils.meetecho.ConferenceManager')
    def test_create_interim_session_conferences_errors(self, mock):
        mock_conf_mgr = mock.return_value
        session = SessionFactory(meeting__type_id='interim')
        timeslot = session.official_timeslotassignment().timeslot

        mock_conf_mgr.create.return_value = []
        with self.assertRaises(RuntimeError):
            create_interim_session_conferences([session])

        mock.reset_mock()
        mock_conf_mgr.create.return_value = [
            Conference(
                manager=mock_conf_mgr, id=1, public_id='some-uuid', description='desc',
                start_time=timeslot.time, duration=timeslot.duration, url='different-fake-meetecho-url',
                deletion_token='please-delete-me',
            ),
            Conference(
                manager=mock_conf_mgr, id=2, public_id='another-uuid', description='desc',
                start_time=timeslot.time, duration=timeslot.duration, url='another-fake-meetecho-url',
                deletion_token='please-delete-me-too',
            ),
        ]
        with self.assertRaises(RuntimeError):
            create_interim_session_conferences([session])

        mock.reset_mock()
        mock_conf_mgr.create.side_effect = ValueError('some error')
        with self.assertRaises(RuntimeError):
            create_interim_session_conferences([session])

    @patch('ietf.meeting.helpers.create_interim_session_conferences')
    def test_sessions_post_save_creates_meetecho_conferences(self, mock_create_method):
        session = SessionFactory(meeting__type_id='interim')
        mock_form = Mock()
        mock_form.instance = session
        mock_form.has_changed.return_value = True
        mock_form.changed_data = []
        mock_form.requires_approval = True

        mock_form.cleaned_data = {'remote_participation': None}
        sessions_post_save(RequestFactory().post('/some/url'), [mock_form])
        self.assertTrue(mock_create_method.called)
        self.assertCountEqual(mock_create_method.call_args[0][0], [])

        mock_create_method.reset_mock()
        mock_form.cleaned_data = {'remote_participation': 'manual'}
        sessions_post_save(RequestFactory().post('/some/url'), [mock_form])
        self.assertTrue(mock_create_method.called)
        self.assertCountEqual(mock_create_method.call_args[0][0], [])

        mock_create_method.reset_mock()
        mock_form.cleaned_data = {'remote_participation': 'meetecho'}
        sessions_post_save(RequestFactory().post('/some/url'), [mock_form])
        self.assertTrue(mock_create_method.called)
        self.assertCountEqual(mock_create_method.call_args[0][0], [session])

        # Check that an exception does not percolate through sessions_post_save
        mock_create_method.side_effect = RuntimeError('some error')
        mock_form.cleaned_data = {'remote_participation': 'meetecho'}
        # create mock request with session / message storage
        request = RequestFactory().post('/some/url')
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        sessions_post_save(request, [mock_form])
        self.assertTrue(mock_create_method.called)
        self.assertCountEqual(mock_create_method.call_args[0][0], [session])
        msgs = [str(msg) for msg in messages]
        self.assertEqual(len(msgs), 1)
        self.assertIn('An error occurred', msgs[0])
