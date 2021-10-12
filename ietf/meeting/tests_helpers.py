# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-
import copy

from django.test import override_settings

from ietf.group.factories import GroupFactory
from ietf.group.models import Group
from ietf.meeting.factories import SessionFactory, MeetingFactory, TimeSlotFactory
from ietf.meeting.helpers import AgendaFilterOrganizer, AgendaKeywordTagger
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
        session_types = ['regular', 'plenary']
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

        # create the ordinary sessions
        for session_type in session_types:
            sess = SessionFactory(group=group, meeting=meeting, type_id=session_type, add_to_schedule=False)
            sess.timeslotassignments.create(
                timeslot=TimeSlotFactory(meeting=meeting, type_id=session_type),
                schedule=meeting.schedule,
            )

        # Create an office hours session in the group's area (i.e., parent). Handle this separately
        # from other session creation to test legacy office hours naming.
        office_hours = SessionFactory(
            name='some office hours',
            group=Group.objects.get(acronym='iesg') if legacy_keywords else expected_area,
            meeting=meeting,
            type_id='other' if legacy_keywords else 'officehours',
            add_to_schedule=False,
        )
        office_hours.timeslotassignments.create(
            timeslot=TimeSlotFactory(meeting=meeting, type_id=office_hours.type_id),
            schedule=meeting.schedule,
        )

        assignments = meeting.schedule.assignments.all()
        orig_num_assignments = len(assignments)

        # Set up historic groups if needed. We've already set the office hours group properly
        # so skip that session. The expected_group will already have its historic_parent set
        # if historic == 'parent'
        if historic:
            for a in assignments:
                if a.session != office_hours:
                    a.session.historic_group = expected_group

        # Execute the method under test
        AgendaKeywordTagger(assignments=assignments).apply()

        # Assert expected results
        self.assertEqual(len(assignments), orig_num_assignments, 'Should not change number of assignments')

        for assignment in assignments:
            expected_filter_keywords = {assignment.slot_type().slug, assignment.session.type.slug}

            if assignment.session == office_hours:
                expected_filter_keywords.update([
                    office_hours.group.acronym,
                    'officehours',
                    'some-officehours' if legacy_keywords else '{}-officehours'.format(expected_area.acronym),
                ])
            else:
                expected_filter_keywords.update([
                    expected_group.acronym,
                    expected_area.acronym
                ])
                if bof:
                    expected_filter_keywords.add('bof')
                token = assignment.session.docname_token_only_for_multiple()
                if token is not None:
                    expected_filter_keywords.update([expected_group.acronym + "-" + token])

            self.assertCountEqual(
                assignment.filter_keywords,
                expected_filter_keywords,
                'Assignment has incorrect filter keywords'
            )

    def test_tag_assignments_with_filter_keywords(self):
        # use distinct meeting numbers > 111 for non-legacy keyword tests
        self.do_test_tag_assignments_with_filter_keywords(112)
        self.do_test_tag_assignments_with_filter_keywords(113, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(114, historic='parent')
        self.do_test_tag_assignments_with_filter_keywords(115, bof=True)
        self.do_test_tag_assignments_with_filter_keywords(116, bof=True, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(117, bof=True, historic='parent')


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
        # set up
        meeting = make_meeting_test_data()

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
            name='FARFUT office hours',
            meeting=meeting
        )

        expected = [
            [
                # area category
                {'label': 'FARFUT', 'keyword': 'farfut', 'is_bof': False,
                 'children': [
                     {'label': 'ames', 'keyword': 'ames', 'is_bof': False},
                     {'label': 'mars', 'keyword': 'mars', 'is_bof': False},
                 ]},
            ],
            [
                # non-area category
                {'label': 'IAB', 'keyword': 'iab', 'is_bof': False,
                 'children': [
                     {'label': iab_child.acronym, 'keyword': iab_child.acronym, 'is_bof': False},
                 ]},
                {'label': 'IRTF', 'keyword': 'irtf', 'is_bof': False,
                 'children': [
                     {'label': irtf_child.acronym, 'keyword': irtf_child.acronym, 'is_bof': True},
                 ]},
            ],
            [
                # non-group category
                {'label': 'Office Hours', 'keyword': 'officehours', 'is_bof': False,
                 'children': [
                     {'label': 'FARFUT', 'keyword': 'farfut-officehours', 'is_bof': False}
                 ]},
                {'label': None, 'keyword': None,'is_bof': False,
                 'children': [
                     {'label': 'BoF', 'keyword': 'bof', 'is_bof': False},
                     {'label': 'Plenary', 'keyword': 'plenary', 'is_bof': False},
                 ]},
            ],
        ]

        # when using sessions instead of assignments, won't get timeslot-type based filters
        expected_with_sessions = copy.deepcopy(expected)
        expected_with_sessions[-1].pop(0)  # pops 'office hours' column

        # put all the above together for single-column tests
        expected_single_category = [
            sorted(sum(expected, []), key=lambda col: col['label'] or 'zzzzz')
        ]
        expected_single_category_with_sessions = [
            sorted(sum(expected_with_sessions, []), key=lambda col: col['label'] or 'zzzzz')
        ]

        ###
        # test using sessions
        sessions = meeting.session_set.all()
        AgendaKeywordTagger(sessions=sessions).apply()

        # default
        filter_organizer = AgendaFilterOrganizer(sessions=sessions)
        self.assertEqual(filter_organizer.get_filter_categories(), expected_with_sessions)

        # single-column
        filter_organizer = AgendaFilterOrganizer(sessions=sessions, single_category=True)
        self.assertEqual(filter_organizer.get_filter_categories(), expected_single_category_with_sessions)

        ###
        # test again using assignments
        assignments = meeting.schedule.assignments.all()
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