# Copyright The IETF Trust 2026, All Rights Reserved

import datetime

from django.conf import settings
from django.utils import timezone

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.template import check_plain_values, render_group_template, value_names
from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import LastCallDocEvent, TelechatDocEvent
from ietf.group.factories import ReviewTeamFactory, RoleFactory
from ietf.person.models import Person
from ietf.review.factories import ReviewAssignmentFactory, ReviewRequestFactory
from ietf.review.template_values import (OpenAssignmentsValues, ReviewAssignedValues,
                                         ReviewContentValues, assignment_values, document_values,
                                         group_values, open_assignment_values, person_values,
                                         reviewer_values, values_class_for_path)
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today


class TemplateValuesTests(TestCase):
    def setUp(self):
        super().setUp()
        self.team = ReviewTeamFactory(acronym="reviewteam", name="Review Team")
        self.reviewer = RoleFactory(group=self.team, name_id="reviewer").email
        self.doc = WgDraftFactory(rev="02")
        self.review_req = ReviewRequestFactory(
            doc=self.doc, team=self.team, type_id="lc", state_id="assigned", requested_rev="01"
        )
        self.assignment = ReviewAssignmentFactory(
            review_request=self.review_req,
            reviewer=self.reviewer,
            state_id="completed",
            result_id="ready",
            reviewed_rev="01",
            completed_on=timezone.now(),
        )
        self.system = Person.objects.get(name="(System)")

    def test_assignment_values(self):
        # Without a last call or a telechat date
        values = assignment_values(self.assignment)
        check_plain_values(values, "values")
        self.assertEqual(values.reviewer.address, self.reviewer.address)
        self.assertEqual(str(values.reviewer), self.reviewer.address)
        self.assertEqual(values.reviewer.person.name, self.reviewer.person.name)
        self.assertEqual(values.reviewer.person.plain_name, self.reviewer.person.plain_name())
        self.assertEqual(values.reviewer.person.ascii, self.reviewer.person.ascii)
        self.assertEqual(str(values.reviewer.person), str(self.reviewer.person))
        self.assertEqual(values.review_request.doc.name, self.doc.name)
        self.assertEqual(values.review_request.doc.rev, "02")
        self.assertEqual(values.review_request.doc.title, self.doc.title)
        self.assertEqual(str(values.review_request.doc), str(self.doc))
        self.assertIsNone(values.review_request.doc.telechat_date)
        self.assertIsNone(values.review_request.doc.most_recent_ietflc)
        self.assertEqual(values.review_request.type.slug, "lc")
        self.assertEqual(values.review_request.type.name, self.review_req.type.name)
        self.assertEqual(values.review_request.deadline, self.review_req.deadline)
        self.assertEqual(values.review_request.requested_rev, "01")
        self.assertEqual(values.state.slug, "completed")
        self.assertEqual(values.result.slug, "ready")
        self.assertEqual(str(values.result), self.assignment.result.name)
        self.assertEqual(values.assigned_on, self.assignment.assigned_on)
        self.assertEqual(values.completed_on, self.assignment.completed_on)
        self.assertEqual(values.reviewed_rev, "01")

        # With both, and without a result
        expires = timezone.now() + datetime.timedelta(days=14)
        LastCallDocEvent.objects.create(
            doc=self.doc, rev=self.doc.rev, type="sent_last_call", by=self.system, expires=expires, desc="Last call sent"
        )
        telechat_date = date_today(settings.TIME_ZONE) + datetime.timedelta(days=7)
        TelechatDocEvent.objects.create(
            doc=self.doc, rev=self.doc.rev, type="scheduled_for_telechat", by=self.system, telechat_date=telechat_date
        )
        self.assignment.result = None
        values = assignment_values(self.assignment)
        check_plain_values(values, "values")
        self.assertEqual(values.review_request.doc.telechat_date, telechat_date)
        self.assertEqual(values.review_request.doc.most_recent_ietflc.expires, expires)
        self.assertIsNone(values.result)

    def test_open_assignment_values(self):
        doc = document_values(self.doc)
        self.assignment.section = "Last calls:"
        self.assignment.lastcall_ends = None
        self.assignment.earlier_review = []
        values = open_assignment_values(self.assignment, doc)
        check_plain_values(values, "values")
        self.assertIs(values.review_request.doc, doc)
        self.assertEqual(values.section, "Last calls:")
        self.assertIsNone(values.lastcall_ends)
        self.assertIs(values.earlier_review, False)
        self.assertEqual(values.earlier_reviews, "")

        self.assignment.lastcall_ends = "2026-03-04"
        self.assignment.earlier_review = [self.assignment]
        self.assignment.earlier_reviews = "(-01 lc reviewed)"
        values = open_assignment_values(self.assignment, doc)
        check_plain_values(values, "values")
        self.assertEqual(values.lastcall_ends, "2026-03-04")
        self.assertIs(values.earlier_review, True)
        self.assertEqual(values.earlier_reviews, "(-01 lc reviewed)")

    def test_values_class_for_path(self):
        for path, values_class in (
            ("/group/reviewteam/email/review_assigned.txt", ReviewAssignedValues),
            ("/group/defaults/email/review_assigned.txt", ReviewAssignedValues),
            ("/group/reviewteam/email/open_assignments.txt", OpenAssignmentsValues),
            ("/group/reviewteam/review/content_templates/lc.txt", ReviewContentValues),
            ("/group/reviewteam/review/content_templates/telechat.txt", ReviewContentValues),
            ("/group/reviewteam/email/other.txt", None),
            ("/nomcom/2026/email/review_assigned.txt", None),
        ):
            self.assertIs(values_class_for_path(path), values_class, msg=path)

    def test_value_names(self):
        self.assertEqual(
            value_names(OpenAssignmentsValues)[:6],
            [
                "group",
                "group.acronym",
                "group.name",
                "review_assignments[]",
                "review_assignments[].reviewer",
                "review_assignments[].reviewer.address",
            ],
        )
        self.assertIn("review_assignments[].section", value_names(OpenAssignmentsValues))
        self.assertIn("rotation_list[].plain_name", value_names(OpenAssignmentsValues))
        self.assertIn("prev_team_reviews[].result.name", value_names(ReviewAssignedValues))

    def test_default_review_assigned_template(self):
        """The default template in the names fixture renders with the values"""
        assigner = RoleFactory(group=self.team, name_id="secr").person
        text = render_group_template(
            DBTemplate.objects.get(path="/group/defaults/email/review_assigned.txt"),
            ReviewAssignedValues(
                assigner=person_values(assigner),
                reviewer=reviewer_values(self.reviewer),
                prev_team_reviews=[assignment_values(self.assignment)],
            ),
        )
        self.assertIn(f"{assigner.ascii} has assigned {self.reviewer.person.ascii} as a reviewer", text)
        self.assertIn("This team has completed other reviews", text)
        self.assertIn(f"{self.reviewer.person.ascii} -01 Ready", text)

    def test_open_assignments_values(self):
        self.assignment.section = "Last calls:"
        self.assignment.lastcall_ends = None
        self.assignment.earlier_review = []
        values = OpenAssignmentsValues(
            group=group_values(self.team),
            review_assignments=[open_assignment_values(self.assignment, document_values(self.doc))],
            rotation_list=[person_values(self.reviewer.person)],
        )
        check_plain_values(values, "values")
        self.assertEqual(values.group.acronym, "reviewteam")
        self.assertEqual(str(values.group), "Review Team")
        self.assertEqual(str(values.rotation_list[0]), self.reviewer.person.plain_name())
