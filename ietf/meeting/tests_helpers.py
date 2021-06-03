# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-
from ietf.group.factories import GroupFactory
from ietf.meeting.factories import SessionFactory, MeetingFactory
from ietf.meeting.helpers import tag_assignments_with_filter_keywords
from ietf.utils.test_utils import TestCase


class HelpersTests(TestCase):
    def do_test_tag_assignments_with_filter_keywords(self, bof=False, historic=None):
        """Assignments should be tagged properly
        
        The historic param can be None, group, or parent, to specify whether to test
        with no historic_group, a historic_group but no historic_parent, or both.
        """
        meeting_types = ['regular', 'plenary']
        group_state_id = 'bof' if bof else 'active'
        group = GroupFactory(state_id=group_state_id)
        historic_group = GroupFactory(state_id=group_state_id)
        historic_parent = GroupFactory(type_id='area')

        if historic == 'parent':
            historic_group.historic_parent = historic_parent

        # Create meeting and sessions
        meeting = MeetingFactory()
        for meeting_type in meeting_types:
            sess = SessionFactory(group=group, meeting=meeting, type_id=meeting_type)
            ts = sess.timeslotassignments.first().timeslot
            ts.type = sess.type
            ts.save()

        # Create an office hours session in the group's area (i.e., parent). This is not
        # currently really needed, but will protect against areas and groups diverging
        # in a way that breaks keywording.
        office_hours = SessionFactory(
            name='some office hours',
            group=group.parent,
            meeting=meeting,
            type_id='other'
        )
        ts = office_hours.timeslotassignments.first().timeslot
        ts.type = office_hours.type
        ts.save()

        assignments = meeting.schedule.assignments.all()
        orig_num_assignments = len(assignments)

        # Set up historic groups if needed
        if historic:
            for a in assignments:
                if a.session != office_hours:
                    a.session.historic_group = historic_group

        # Execute the method under test
        tag_assignments_with_filter_keywords(assignments)

        # Assert expected results
        self.assertEqual(len(assignments), orig_num_assignments, 'Should not change number of assignments')

        if historic:
            expected_group = historic_group
            expected_area = historic_parent if historic == 'parent' else historic_group.parent
        else:
            expected_group = group
            expected_area = group.parent

        for assignment in assignments:
            expected_filter_keywords = {assignment.timeslot.type.slug, assignment.session.type.slug}

            if assignment.session == office_hours:
                expected_filter_keywords.update([
                    group.parent.acronym,
                    'officehours',
                    'someofficehours',
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
        self.do_test_tag_assignments_with_filter_keywords()
        self.do_test_tag_assignments_with_filter_keywords(historic='group')
        self.do_test_tag_assignments_with_filter_keywords(historic='parent')
        self.do_test_tag_assignments_with_filter_keywords(bof=True)
        self.do_test_tag_assignments_with_filter_keywords(bof=True, historic='group')
        self.do_test_tag_assignments_with_filter_keywords(bof=True, historic='parent')
