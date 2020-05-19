# Copyright The IETF Trust 2016-2019, All Rights Reserved

import debug                            # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory, IndividualDraftFactory
from ietf.group.factories import ReviewTeamFactory
from ietf.group.models import Group, Role
from ietf.name.models import ReviewerQueuePolicyName
from ietf.person.factories import PersonFactory
from ietf.person.fields import PersonEmailChoiceField
from ietf.person.models import Email
from ietf.review.factories import ReviewAssignmentFactory, ReviewRequestFactory
from ietf.review.models import ReviewerSettings, NextReviewerInTeam, UnavailablePeriod, ReviewWish, \
    ReviewTeamSettings
from ietf.review.policies import (AssignmentOrderResolver, LeastRecentlyUsedReviewerQueuePolicy,
                                  RotateAlphabeticallyReviewerQueuePolicy,
                                  get_reviewer_queue_policy)
from ietf.utils.test_data import create_person
from ietf.utils.test_utils import TestCase


class GetReviewerQueuePolicyTest(TestCase):
    def test_valid_policy(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"), settings__reviewer_queue_policy_id='LeastRecentlyUsed')
        policy = get_reviewer_queue_policy(team)
        self.assertEqual(policy.__class__, LeastRecentlyUsedReviewerQueuePolicy)
        
    def test_missing_settings(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        ReviewTeamSettings.objects.all().delete()
        with self.assertRaises(ValueError):
            get_reviewer_queue_policy(team)
            
    def test_invalid_policy_name(self):
        ReviewerQueuePolicyName.objects.create(slug='invalid')
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"), settings__reviewer_queue_policy_id='invalid')
        with self.assertRaises(ValueError):
            get_reviewer_queue_policy(team)


class RotateAlphabeticallyReviewerAndGenericQueuePolicyTest(TestCase):
    """
    These tests also cover the common behaviour in AbstractReviewerQueuePolicy,
    as that's difficult to test on it's own.
    """
    def test_default_reviewer_rotation_list(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        policy = RotateAlphabeticallyReviewerQueuePolicy(team)

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
            availability='unavailable',
        )
        # This should not have any impact. Canfinish unavailable reviewers are included in
        # the default rotation, and filtered further when making assignment choices.
        UnavailablePeriod.objects.create(
            team=team,
            person=reviewers[1],
            start_date='2000-01-01',
            availability='canfinish',
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
        policy = RotateAlphabeticallyReviewerQueuePolicy(team)
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
        policy = RotateAlphabeticallyReviewerQueuePolicy(team)
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
        policy = RotateAlphabeticallyReviewerQueuePolicy(team)

        # make a bunch of reviewers
        reviewers = [
            create_person(team, "reviewer", name="Test Reviewer{}".format(i), username="testreviewer{}".format(i))
            for i in range(5)
        ]

        self.assertEqual(reviewers, policy.default_reviewer_rotation_list())

        def reviewer_settings_for(person):
            return (ReviewerSettings.objects.filter(team=team, person=person).first()
                    or ReviewerSettings(team=team, person=person))

        def get_skip_next(person):
            return reviewer_settings_for(person).skip_next

        # Regular in-order assignment without skips
        reviewer0_settings = reviewer_settings_for(reviewers[0])
        reviewer0_settings.request_assignment_next = True
        reviewer0_settings.save()
        policy.update_policy_state_for_assignment(assignee_person=reviewers[0], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[1])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 0)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)
        # request_assignment_next should be reset after any assignment
        self.assertFalse(reviewer_settings_for(reviewers[0]).request_assignment_next)

        # In-order assignment with add_skip
        policy.update_policy_state_for_assignment(assignee_person=reviewers[1], add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)  # from current add_skip=True
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # In-order assignment to 2, but 3 has a skip_next, so 4 should be assigned.
        # 3 has skip_next decreased as it is skipped over, 1 retains its skip_next
        reviewer3_settings = reviewer_settings_for(reviewers[3])
        reviewer3_settings.skip_next = 2
        reviewer3_settings.save()
        policy.update_policy_state_for_assignment(assignee_person=reviewers[2], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)  # from previous add_skip=true
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)  # from manually set skip_next - 1
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # Out of order assignments, nothing should change,
        # except the add_skip=True should still apply
        policy.update_policy_state_for_assignment(assignee_person=reviewers[3], add_skip=False)
        policy.update_policy_state_for_assignment(assignee_person=reviewers[2], add_skip=False)
        policy.update_policy_state_for_assignment(assignee_person=reviewers[1], add_skip=False)
        policy.update_policy_state_for_assignment(assignee_person=reviewers[0], add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 1)  # from current add_skip=True
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)
        self.assertEqual(get_skip_next(reviewers[4]), 0)
        
        # Regular assignment, testing wrap-around
        policy.update_policy_state_for_assignment(assignee_person=reviewers[4], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)  # skipped over with this assignment
        self.assertEqual(get_skip_next(reviewers[1]), 0)  # skipped over with this assignment
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # Leave only a single reviewer remaining, which should not trigger an infinite loop.
        # The deletion also causes NextReviewerInTeam to be deleted.
        [reviewer.delete() for reviewer in reviewers[1:]]
        self.assertEqual([reviewers[0]], policy.default_reviewer_rotation_list())
        policy.update_policy_state_for_assignment(assignee_person=reviewers[0], add_skip=False)
        # No NextReviewerInTeam should be created, the only possible next is the excluded assignee.
        self.assertFalse(NextReviewerInTeam.objects.filter(team=team))
        self.assertEqual([reviewers[0]], policy.default_reviewer_rotation_list())

    def test_return_reviewer_to_rotation_top(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team",
                                 list_email="rotationteam@ietf.org",
                                 parent=Group.objects.get(acronym="farfut"))
        reviewer = create_person(team, "reviewer", name="reviewer", username="reviewer")
        policy = RotateAlphabeticallyReviewerQueuePolicy(team)
        policy.return_reviewer_to_rotation_top(reviewer)
        self.assertTrue(ReviewerSettings.objects.get(person=reviewer).request_assignment_next)
        
        
class LeastRecentlyUsedReviewerQueuePolicyTest(TestCase):
    """
    These tests only cover where this policy deviates from
    RotateAlphabeticallyReviewerQueuePolicy - the common behaviour
    inherited from AbstractReviewerQueuePolicy is covered in
    RotateAlphabeticallyReviewerQueuePolicyTest.
    """
    def test_default_reviewer_rotation_list(self):
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team",
                                 list_email="rotationteam@ietf.org",
                                 parent=Group.objects.get(acronym="farfut"))
        policy = LeastRecentlyUsedReviewerQueuePolicy(team)

        reviewers = [
            create_person(team, "reviewer", name="Test Reviewer{}".format(i),
                          username="testreviewer{}".format(i))
            for i in range(5)
        ]

        # This reviewer should never be included.
        unavailable_reviewer = create_person(team, "reviewer", name="unavailable reviewer",
                                             username="unavailablereviewer")
        UnavailablePeriod.objects.create(
            team=team,
            person=unavailable_reviewer,
            start_date='2000-01-01',
            availability='unavailable',
        )
        # This should not have any impact. Canfinish unavailable reviewers are included in
        # the default rotation, and filtered further when making assignment choices.
        UnavailablePeriod.objects.create(
            team=team,
            person=reviewers[1],
            start_date='2000-01-01',
            availability='canfinish',
        )
        # This reviewer has an assignment, but is no longer in the team and should not be in rotation.
        out_of_team_reviewer = PersonFactory()
        ReviewAssignmentFactory(review_request__team=team, reviewer=out_of_team_reviewer.email())

        # No known assignments, order in PK order.
        rotation = policy.default_reviewer_rotation_list()
        self.assertNotIn(unavailable_reviewer, rotation)
        self.assertEqual(rotation, reviewers)
        
        # Regular accepted assignments. Note that one is older and one is newer than reviewer 0's,
        # the newest one should count for ordering, i.e. reviewer 1 should be later in the list.
        ReviewAssignmentFactory(reviewer=reviewers[1].email(), assigned_on='2019-01-01',
                                state_id='accepted', review_request__team=team)
        ReviewAssignmentFactory(reviewer=reviewers[1].email(), assigned_on='2017-01-01',
                                state_id='accepted', review_request__team=team)
        # Rejected assignment, should not affect reviewer 2's position
        ReviewAssignmentFactory(reviewer=reviewers[2].email(), assigned_on='2020-01-01',
                                state_id='rejected', review_request__team=team)
        # Completed assignments, assigned before the most recent assignment of reviewer 1,
        # but completed after (assign date should count).
        ReviewAssignmentFactory(reviewer=reviewers[0].email(), assigned_on='2018-01-01',
                                completed_on='2020-01-01', state_id='completed',
                                review_request__team=team)
        ReviewAssignmentFactory(reviewer=reviewers[0].email(), assigned_on='2018-05-01',
                                completed_on='2020-01-01', state_id='completed',
                                review_request__team=team)
        rotation = policy.default_reviewer_rotation_list()
        self.assertNotIn(unavailable_reviewer, rotation)
        self.assertEqual(rotation, [reviewers[2], reviewers[3], reviewers[4], reviewers[0], reviewers[1]])

    def test_return_reviewer_to_rotation_top(self):
        # Should do nothing, this is implicit in this policy, no state change is needed.
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team",
                                 list_email="rotationteam@ietf.org",
                                 parent=Group.objects.get(acronym="farfut"))
        reviewer = create_person(team, "reviewer", name="reviewer", username="reviewer")
        policy = LeastRecentlyUsedReviewerQueuePolicy(team)
        policy.return_reviewer_to_rotation_top(reviewer)


class AssignmentOrderResolverTests(TestCase):
    def test_determine_ranking(self):
        # reviewer_high is second in the default rotation, reviewer_low is first
        # however, reviewer_high hits every score increase, reviewer_low hits every score decrease
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        reviewer_high = create_person(team, "reviewer", name="Test Reviewer-high", username="testreviewerhigh")
        reviewer_low = create_person(team, "reviewer", name="Test Reviewer-low", username="testreviewerlow")
        reviewer_unavailable = create_person(team, "reviewer", name="Test Reviewer-unavailable", username="testreviewerunavailable")
        # This reviewer should be entirely ignored because it is not in the rotation list.
        create_person(team, "reviewer", name="Test Reviewer-out-of-rotation", username="testreviewer-out-of-rotation")

        # Create a document with ancestors, that also triggers author check, AD check and group check
        doc_individual = IndividualDraftFactory()
        doc_wg = WgDraftFactory(relations=[('replaces', doc_individual)])
        doc_middle_wg = WgDraftFactory(relations=[('replaces', doc_wg)])
        doc = WgDraftFactory(group__acronym='mars', rev='01', authors=[reviewer_low], ad=reviewer_low, shepherd=reviewer_low.email(), relations=[('replaces', doc_middle_wg)])
        Role.objects.create(group=doc.group, person=reviewer_low, email=reviewer_low.email(), name_id='advisor')
        
        # Trigger previous review check (including finding ancestor documents) and completed review stats.
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc_individual, reviewer=reviewer_high.email(), state_id='completed')
        # Trigger other review stats
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_high.email(), state_id='no-response')
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_high.email(), state_id='part-completed')
        # Trigger review wish check
        ReviewWish.objects.create(team=team, doc=doc, person=reviewer_high)
        
        # This period should not have an impact, because it is the canfinish type,
        # and this reviewer has reviewed previously.
        UnavailablePeriod.objects.create(
            team=team,
            person=reviewer_high,
            start_date='2000-01-01',
            availability='canfinish',
        )
        # This period should exclude this reviewer entirely, as it is 'canfinish',
        # but this reviewer has not reviewed previously.
        UnavailablePeriod.objects.create(
            team=team,
            person=reviewer_unavailable,
            start_date='2000-01-01',
            availability='canfinish',
        )
        # Trigger "reviewer has rejected before"
        ReviewAssignmentFactory(review_request__team=team, review_request__doc=doc, reviewer=reviewer_low.email(), state_id='rejected')

        # Trigger max frequency and open review stats
        ReviewAssignmentFactory(review_request__team=team, reviewer=reviewer_low.email(), state_id='assigned', review_request__doc__pages=10)
        # Trigger skip_next, max frequency, filter_re
        ReviewerSettings.objects.create(
            team=team,
            person=reviewer_low,
            filter_re='.*draft.*',
            skip_next=2,
            min_interval=91,
        )
        # Trigger "assign me next"
        ReviewerSettings.objects.create(
            team=team,
            person=reviewer_high,
            request_assignment_next=True,
        )

        review_req = ReviewRequestFactory(doc=doc, team=team, type_id='early')
        rotation_list = [reviewer_low, reviewer_high, reviewer_unavailable]

        order = AssignmentOrderResolver(Email.objects.all(), review_req, rotation_list)
        ranking = order.determine_ranking()
        self.assertEqual(len(ranking), 2)
        self.assertEqual(ranking[0]['email'], reviewer_high.email())
        self.assertEqual(ranking[1]['email'], reviewer_low.email())
        # These scores follow the ordering of https://trac.tools.ietf.org/tools/ietfdb/wiki/ReviewerQueuePolicy,
        self.assertEqual(ranking[0]['scores'], [ 1,  1,  1,  1,  1,  1,   0,  0, -1])
        self.assertEqual(ranking[1]['scores'], [-1, -1, -1, -1, -1, -1, -91, -2,  0])
        self.assertEqual(ranking[0]['label'], 'Test Reviewer-high: unavailable indefinitely (Can do follow-ups); requested to be selected next for assignment; reviewed document before; wishes to review document; #2; 1 no response, 1 partially complete, 1 fully completed')
        self.assertEqual(ranking[1]['label'], 'Test Reviewer-low: rejected review of document before; is author of document; filter regexp matches; max frequency exceeded, ready in 91 days; skip next 2; #1; currently 1 open, 10 pages')
