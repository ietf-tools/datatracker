# Copyright The IETF Trust 2016-2019, All Rights Reserved

import datetime

from ietf.doc.factories import WgDraftFactory
from ietf.group.factories import ReviewTeamFactory
from ietf.group.models import Group, Role
from ietf.person.fields import PersonEmailChoiceField
from ietf.person.models import Email
from ietf.review.factories import ReviewAssignmentFactory, ReviewRequestFactory
from ietf.review.models import ReviewerSettings, NextReviewerInTeam, UnavailablePeriod, \
    ReviewRequest, ReviewWish
from ietf.review.policies import get_reviewer_queue_policy, AssignmentOrderResolver
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
        
        # This reviewer should never be included.
        unavailable_reviewer = create_person(team, "reviewer", name="unavailable reviewer", username="unavailablereviewer")
        UnavailablePeriod.objects.create(
            team=team,
            person=unavailable_reviewer,
            start_date='2000-01-01',
            availability=UnavailablePeriod.AVAILABILITY_CHOICES[0],
        )

        # Default policy without a NextReviewerInTeam
        rotation = policy.default_reviewer_rotation_list()
        self.assertNotIn(unavailable_reviewer, rotation)
        self.assertEqual(rotation, reviewers)

        # Policy with a current NextReviewerInTeam
        NextReviewerInTeam.objects.create(team=team, next_reviewer=reviewers[3])
        rotation = policy.default_reviewer_rotation_list()
        self.assertNotIn(unavailable_reviewer, rotation)
        self.assertEqual(rotation, reviewers[3:] + reviewers[:3])

        # Policy with a NextReviewerInTeam that has left the team.
        Role.objects.get(person=reviewers[1]).delete()
        NextReviewerInTeam.objects.filter(team=team).update(next_reviewer=reviewers[1])
        rotation = policy.default_reviewer_rotation_list()
        self.assertNotIn(unavailable_reviewer, rotation)
        self.assertEqual(rotation, reviewers[2:] + reviewers[:1])
    
    def test_setup_reviewer_field(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        policy = get_reviewer_queue_policy(team)
        reviewer_0 = create_person(team, "reviewer", name="Test Reviewer-0", username="testreviewer0")
        reviewer_1 = create_person(team, "reviewer", name="Test Reviewer-1", username="testreviewer1")
        review_req = ReviewRequestFactory(team=team, type_id='early')
        ReviewAssignmentFactory(review_request=review_req, reviewer=reviewer_1.email(), state_id='part-completed')
        field = PersonEmailChoiceField(label="Assign Reviewer", empty_label="(None)", required=False)
        
        policy.setup_reviewer_field(field, review_req)
        self.assertEqual(field.choices[0], ('', '(None)'))
        self.assertEqual(field.choices[1][0], str(reviewer_0.email()))
        self.assertEqual(field.choices[2][0], str(reviewer_1.email()))
        self.assertEqual(field.choices[1][1], 'Test Reviewer-0: #1')
        self.assertEqual(field.choices[2][1], 'Test Reviewer-1: #2; 1 partially complete')
        self.assertEqual(field.initial, str(reviewer_1.email()))
        
    def test_recommended_assignment_order(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        policy = get_reviewer_queue_policy(team)
        reviewer_high = create_person(team, "reviewer", name="Test Reviewer-1-high", username="testreviewerhigh")
        reviewer_low = create_person(team, "reviewer", name="Test Reviewer-0-low", username="testreviewerlow")
        
        # reviewer_high appears later in the default rotation, but reviewer_low is the author
        doc = WgDraftFactory(group__acronym='mars', rev='01', authors=[reviewer_low])
        review_req = ReviewRequestFactory(doc=doc, team=team, type_id='early')

        order = policy.recommended_assignment_order(Email.objects.all(), review_req)
        self.assertEqual(order[0][0], str(reviewer_high.email()))
        self.assertEqual(order[1][0], str(reviewer_low.email()))
        self.assertEqual(order[0][1], 'Test Reviewer-1-high: #2')
        self.assertEqual(order[1][1], 'Test Reviewer-0-low: is author of document; #1')

        with self.assertRaises(ValueError):
            review_req_other_team = ReviewRequestFactory(doc=doc, type_id='early')
            policy.recommended_assignment_order(Email.objects.all(), review_req_other_team)

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
        

class AssignmentOrderResolverTests(TestCase):
    def test_determine_ranking(self):
        # reviewer_high is second in the default rotation, reviewer_low is first
        # however, reviewer_high hits every score increase, reviewer_low hits every score decrease
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        reviewer_high = create_person(team, "reviewer", name="Test Reviewer-high", username="testreviewerhigh")
        reviewer_low = create_person(team, "reviewer", name="Test Reviewer-low", username="testreviewerlow")

        # Trigger author check, AD check and group check
        doc = WgDraftFactory(group__acronym='mars', rev='01', authors=[reviewer_low], ad=reviewer_low, shepherd=reviewer_low.email())
        Role.objects.create(group=doc.group, person=reviewer_low, email=reviewer_low.email(), name_id='advisor')
        
        review_req = ReviewRequestFactory(doc=doc, team=team, type_id='early')
        rotation_list = [reviewer_low, reviewer_high]
        
        # Trigger previous review check and completed review stats - TODO: something something related documents
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_high.email(), state_id='completed')
        # Trigger other review stats
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_high.email(), state_id='no-response')
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_high.email(), state_id='part-completed')
        # Trigger review wish check
        ReviewWish.objects.create(team=team, doc=doc, person=reviewer_high)
        
        # Trigger max frequency and open review stats
        ReviewAssignmentFactory(review_request__team=team, reviewer=reviewer_low.email(), state_id='assigned', review_request__doc__pages=10)
        # Trigger skip_next, max frequency and filter_re
        ReviewerSettings.objects.create(
            team=team,
            person=reviewer_low,
            filter_re='.*draft.*',
            skip_next=2,
            min_interval=91,
        )

        order = AssignmentOrderResolver(Email.objects.all(), review_req, rotation_list)
        ranking = order.determine_ranking()
        self.assertEqual(ranking[0]['email'], reviewer_high.email())
        self.assertEqual(ranking[1]['email'], reviewer_low.email())
        self.assertEqual(ranking[0]['scores'], [ 1,  1,  1,  1,   0,  0, -1])
        self.assertEqual(ranking[1]['scores'], [-1, -1, -1, -1, -91, -2,  0])
        self.assertEqual(ranking[0]['label'], 'Test Reviewer-high: reviewed document before; wishes to review document; #2; 1 no response, 1 partially complete, 1 fully completed')
        self.assertEqual(ranking[1]['label'], 'Test Reviewer-low: is author of document; filter regexp matches; max frequency exceeded, ready in 91 days; skip next 2; #1; currently 1 open, 10 pages')
