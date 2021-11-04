# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.conf import settings
from django.test import override_settings

from ietf.group.factories import GroupFactory
from ietf.group.models import Group
from ietf.meeting.factories import SessionFactory, MeetingFactory, TimeSlotFactory
from ietf.meeting.helpers import AgendaFilterOrganizer, AgendaKeywordTagger
from ietf.meeting.models import SchedTimeSessAssignment
from ietf.meeting.test_data import make_meeting_test_data
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