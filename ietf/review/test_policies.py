# Copyright The IETF Trust 2016-2019, All Rights Reserved

import datetime

from ietf.doc.factories import WgDraftFactory
from ietf.group.factories import ReviewTeamFactory
from ietf.group.models import Group, Role
from ietf.review.factories import ReviewAssignmentFactory
from ietf.review.models import ReviewerSettings, NextReviewerInTeam, UnavailablePeriod, \
    ReviewRequest
from ietf.review.policies import get_reviewer_queue_policy
from ietf.utils.test_data import create_person
from ietf.utils.test_utils import TestCase


class RotateWithSkipReviewerPolicyTests(TestCase):
    def test_default_reviewer_rotation_list(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        policy = get_reviewer_queue_policy(team)

        reviewers = [
            create_person(team, "reviewer", name="Test Reviewer{}".format(i), username="testreviewer{}".format(i))
            for i in range(5)
        ]
        reviewers_pks = [r.pk for r in reviewers]
        
        # This reviewer should never be included.
        unavailable_reviewer = create_person(team, "reviewer", name="unavailable reviewer", username="unavailablereviewer")
        UnavailablePeriod.objects.create(
            team=team,
            person=unavailable_reviewer,
            start_date='2000-01-01',
            end_date='3000-01-01',
            availability=UnavailablePeriod.AVAILABILITY_CHOICES[0],
        )

        # Default policy without a NextReviewerInTeam
        rotation = policy.default_reviewer_rotation_list(skip_unavailable=True)
        self.assertNotIn(unavailable_reviewer.pk, rotation)
        self.assertEqual(rotation, reviewers_pks)

        # Policy with a current NextReviewerInTeam
        NextReviewerInTeam.objects.create(team=team, next_reviewer=reviewers[3])
        rotation = policy.default_reviewer_rotation_list(skip_unavailable=True)
        self.assertNotIn(unavailable_reviewer.pk, rotation)
        self.assertEqual(rotation, reviewers_pks[3:] + reviewers_pks[:3])

        # Policy with a NextReviewerInTeam that has left the team.
        Role.objects.get(person=reviewers[1]).delete()
        NextReviewerInTeam.objects.filter(team=team).update(next_reviewer=reviewers[1])
        rotation = policy.default_reviewer_rotation_list(skip_unavailable=True)
        self.assertNotIn(unavailable_reviewer.pk, rotation)
        self.assertEqual(rotation, reviewers_pks[2:] + reviewers_pks[:1])

    def test_update_policy_state_for_assignment(self):

        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        policy = get_reviewer_queue_policy(team)
        doc = WgDraftFactory()

        # make a bunch of reviewers
        reviewers = [
            create_person(team, "reviewer", name="Test Reviewer{}".format(i), username="testreviewer{}".format(i))
            for i in range(5)
        ]

        self.assertEqual(reviewers, policy.default_reviewer_rotation_list())

        def get_skip_next(person):
            settings = (ReviewerSettings.objects.filter(team=team, person=person).first()
                        or ReviewerSettings(team=team))
            return settings.skip_next

        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[0].pk, add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[1])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 0)

        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[1].pk, add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)

        # skip reviewer 2
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[3].pk, add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)

        # pick reviewer 2, use up reviewer 3's skip_next
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[2].pk, add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # check wrap-around
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[4].pk)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[0])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # unavailable
        today = datetime.date.today()
        UnavailablePeriod.objects.create(team=team, person=reviewers[1], start_date=today, end_date=today, availability="unavailable")
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[0].pk)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1) # don't consume that skip while the reviewer is unavailable
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # pick unavailable anyway
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[1].pk, add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # not through min_interval so advance past reviewer[2]
        settings, _ = ReviewerSettings.objects.get_or_create(team=team, person=reviewers[2])
        settings.min_interval = 30
        settings.save()
        req = ReviewRequest.objects.create(team=team, doc=doc, type_id="early", state_id="assigned", deadline=today, requested_by=reviewers[0])
        ReviewAssignmentFactory(review_request=req, state_id="accepted", reviewer = reviewers[2].email_set.first(),assigned_on = req.time)
        policy.update_policy_state_for_assignment(assignee_person_id=reviewers[3].pk)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)