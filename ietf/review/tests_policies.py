# Copyright The IETF Trust 2016-2021, All Rights Reserved

import debug                            # pyflakes:ignore
import datetime

from django.utils import timezone

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
                                  get_reviewer_queue_policy, QUEUE_POLICY_NAME_MAPPING)
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


class _Wrapper(TestCase):
    """Wrapper class - exists to prevent UnitTest from trying to run the base class tests"""

    def test_all_reviewer_queue_policies_have_tests(self):
        """Every ReviewerQueuePolicy should be tested"""
        rqp_test_classes = self.ReviewerQueuePolicyTestCase.__subclasses__() 
        
        self.assertCountEqual(
            QUEUE_POLICY_NAME_MAPPING.keys(),
            [cls.reviewer_queue_policy_id for cls in rqp_test_classes],
        )

    class ReviewerQueuePolicyTestCase(TestCase):
        """Parent class to define interface / default tests for QueuePolicy implementation tests
        
        To add tests for a new AbstractReviewerQueuePolicy class, you need to:
          1. Subclass _Wrapper.ReviewerQueuePolicyTestCase (i.e., this class)
          2. Define the reviewer_queue_policy_id class variable in your new class
          3. (Maybe) implement a class-specific append_reviewer() method to add a new
             reviewer that sorts to the end of default_reviewer_rotation_list()
          4. Fill in any tests that raise NotImplemented exceptions
          5. Override any other tests that should have different behavior for your new policy
          6. Add any policy-specific tests
          
          When adding tests to this default class, be careful not to make assumptions about
          the ordering of reviewers. The only guarantee is that append_reviewer() adds a
          new reviewer who is later in the default rotation for the next assignment. Once that
          assignment is made, the rotation order is entirely unknown! If you need to make
          such assumptions, call policy.default_reviewer_rotation_list() or move the test
          into a policy-specific subclass.
        """

        # Must define reviewer_queue_policy_id in test subclass
        reviewer_queue_policy_id = ''

        def setUp(self):
            self.team = ReviewTeamFactory(acronym="rotationteam", 
                                          name="Review Team",
                                          list_email="rotationteam@ietf.org", 
                                          parent=Group.objects.get(acronym="farfut"))
            self.team.reviewteamsettings.reviewer_queue_policy_id = self.reviewer_queue_policy_id 
            self.team.reviewteamsettings.save()
            
            self.policy = get_reviewer_queue_policy(self.team)
            self.reviewers = []

        def append_reviewer(self, skip_count=None):
            """Create a reviewer who will appear in the assignee options list
            
            Newly added reviewer must come later in the default_reviewer_rotation_list. The default
            implementation creates users whose names are in lexicographic order. 
            """
            index = len(self.reviewers)
            assert(index < 100)  # ordering by label will fail if > 100 reviewers are created
            label = '{:02d}'.format(index)
            reviewer = create_person(self.team,
                                     'reviewer',
                                     name='Test Reviewer{}'.format(label),
                                     username='testreviewer{}'.format(label))
            self.reviewers.append(reviewer)
            if skip_count is not None:
                settings = self.reviewer_settings_for(reviewer)
                settings.skip_next = skip_count
                settings.save()
            return reviewer

        def create_old_review_assignment(self, reviewer, **kwargs):
            """Create a review that won't disturb the ordering of reviewers"""
            return ReviewAssignmentFactory(reviewer=reviewer.email(), **kwargs)

        def reviewer_settings_for(self, person):
            return (ReviewerSettings.objects.filter(team=self.team, person=person).first()
                    or ReviewerSettings(team=self.team, person=person))

        def test_return_reviewer_to_rotation_top(self):
            # Subclass must implement this
            raise NotImplementedError

        def test_default_reviewer_rotation_list_ignores_out_of_team_reviewers(self):
            available_reviewers, _ = self.set_up_default_reviewer_rotation_list_test()
    
            # This reviewer has an assignment, but is no longer in the team and should not be in rotation.
            out_of_team_reviewer = PersonFactory()
            ReviewAssignmentFactory(review_request__team=self.team, reviewer=out_of_team_reviewer.email())
    
            # No known assignments, order in PK order.
            rotation = self.policy.default_reviewer_rotation_list()
            self.assertNotIn(out_of_team_reviewer, rotation)
            self.assertEqual(rotation, available_reviewers)

        def test_assign_reviewer(self):
            """assign_reviewer() should create a review assignment for the correct user"""
            review_req = ReviewRequestFactory(team=self.team)
            for _ in range(3):
                self.append_reviewer()

            self.assertFalse(review_req.reviewassignment_set.exists())

            reviewer = self.reviewers[0]
            self.policy.assign_reviewer(review_req, reviewer.email(), add_skip=False)
            self.assertCountEqual(
                review_req.reviewassignment_set.all().values_list('reviewer', flat=True),
                [str(reviewer.email())]
            )
            self.assertEqual(self.reviewer_settings_for(reviewer).skip_next, 0)

        def test_assign_reviewer_and_add_skip(self):
            """assign_reviewer() should create a review assignment for the correct user"""
            review_req = ReviewRequestFactory(team=self.team)
            for _ in range(3):
                self.append_reviewer()

            self.assertFalse(review_req.reviewassignment_set.exists())

            reviewer = self.reviewers[0]
            self.policy.assign_reviewer(review_req, reviewer.email(), add_skip=True)
            self.assertCountEqual(
                review_req.reviewassignment_set.all().values_list('reviewer', flat=True),
                [str(reviewer.email())]
            )
            self.assertEqual(self.reviewer_settings_for(reviewer).skip_next, 1)

        def test_assign_reviewer_updates_skip_next_minimal(self):
            """If we skip the first reviewer, their skip_next value should decrement
            
            Different policies handle skipping in different ways. 
            
            The only assumption we make in the base test class is that an in-order assignment
            to a non-skipped reviewer will decrement the skip_next for any reviewers we skipped.
            Any other tests are policy-specific (e.g., the RotateAlphabetically policy will
            also decrement any users skipped between the assignee and the next reviewer in the
            rotation) 
            """
            review_req = ReviewRequestFactory(team=self.team)

            reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(reviewer_to_skip)
            settings.skip_next = 1
            settings.save()

            another_reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(another_reviewer_to_skip)
            settings.skip_next = 1
            settings.save()

            reviewer_to_assign = self.append_reviewer()
            reviewer_to_ignore = self.append_reviewer()

            # Check test assumptions
            self.assertEqual(
                self.policy.default_reviewer_rotation_list(),
                [
                    reviewer_to_skip,
                    another_reviewer_to_skip,
                    reviewer_to_assign,
                    reviewer_to_ignore,
                ],
            )
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 1)
            self.assertEqual(self.reviewer_settings_for(another_reviewer_to_skip).skip_next, 1)
            self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0)
            
            self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=False)

            # Check results
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                             'skip_next not updated for first skipped reviewer')
            self.assertEqual(self.reviewer_settings_for(another_reviewer_to_skip).skip_next, 0,
                             'skip_next not updated for second skipped reviewer')

        def test_assign_reviewer_updates_skip_next_with_add_skip(self):
            """Skipping reviewers with add_skip=True should update skip_counts properly
            
            Subclasses must implement
            """
            raise NotImplementedError

        def test_assign_reviewer_updates_skip_next_without_add_skip(self):
            """Skipping reviewers with add_skip=False should update skip_counts properly
            
            Subclasses must implement
            """
            raise NotImplementedError

        def test_assign_reviewer_ignores_skip_next_on_out_of_order_assignment(self):
            """If assignment is not in-order, skip_next values should not change"""
            review_req = ReviewRequestFactory(team=self.team)

            reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(reviewer_to_skip)
            settings.skip_next = 1
            settings.save()

            reviewer_to_ignore = self.append_reviewer()

            reviewer_to_assign = self.append_reviewer()

            another_reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(another_reviewer_to_skip)
            settings.skip_next = 3
            settings.save()

            # Check test assumptions
            self.assertEqual(
                self.policy.default_reviewer_rotation_list(),
                [
                    reviewer_to_skip,
                    reviewer_to_ignore,
                    reviewer_to_assign,
                    another_reviewer_to_skip,
                ],
            )
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 1)
            self.assertEqual(self.reviewer_settings_for(reviewer_to_ignore).skip_next, 0)
            self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0)
            self.assertEqual(self.reviewer_settings_for(another_reviewer_to_skip).skip_next, 3)

            self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=False)

            # Check results
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 1,
                             'skip_next changed unexpectedly for first skipped reviewer')
            self.assertEqual(self.reviewer_settings_for(reviewer_to_ignore).skip_next, 0,
                             'skip_next changed unexpectedly for ignored reviewer')
            self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0,
                             'skip_next changed unexpectedly for assigned reviewer')
            self.assertEqual(self.reviewer_settings_for(another_reviewer_to_skip).skip_next, 3,
                             'skip_next changed unexpectedly for second skipped reviewer')

        def test_assign_reviewer_updates_skip_next_when_canfinish_other_doc(self):
            """Should update skip_next when 'canfinish' set for someone unrelated to this doc"""
            completed_req = ReviewRequestFactory(team=self.team, state_id='assigned')
            assigned_req = ReviewRequestFactory(team=self.team, state_id='assigned')
            new_req = ReviewRequestFactory(team=self.team, doc=assigned_req.doc)

            reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(reviewer_to_skip)
            settings.skip_next = 1
            settings.save()

            # Has completed a review of some other document - unavailable for current req
            canfinish_reviewer = self.append_reviewer()
            UnavailablePeriod.objects.create(
                team=self.team,
                person=canfinish_reviewer,
                start_date='2000-01-01',
                availability='canfinish',
            )
            self.create_old_review_assignment(
                reviewer=canfinish_reviewer,
                review_request=completed_req,
                state_id='completed',
            )

            # Has no review assignments at all
            canfinish_reviewer_no_review = self.append_reviewer()
            UnavailablePeriod.objects.create(
                team=self.team,
                person=canfinish_reviewer_no_review,
                start_date='2000-01-01',
                availability='canfinish',
            )

            # Has accepted but not completed a review of this document
            canfinish_reviewer_no_completed = self.append_reviewer()
            UnavailablePeriod.objects.create(
                team=self.team,
                person=canfinish_reviewer_no_completed,
                start_date='2000-01-01',
                availability='canfinish',
            )
            self.create_old_review_assignment(
                reviewer=canfinish_reviewer_no_completed,
                review_request=assigned_req,
                state_id='accepted',
            )

            reviewer_to_assign = self.append_reviewer()

            self.assertEqual(
                self.policy.default_reviewer_rotation_list(),
                [
                    reviewer_to_skip, 
                    canfinish_reviewer,
                    canfinish_reviewer_no_review,
                    canfinish_reviewer_no_completed,
                    reviewer_to_assign
                ],
                'Test logic error - reviewers not in expected starting order'
            )

        # assign the review
            self.policy.assign_reviewer(new_req, reviewer_to_assign.email(), add_skip=False)

            # Check results
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                             'skip_next not updated for skipped reviewer')
            self.assertEqual(self.reviewer_settings_for(canfinish_reviewer).skip_next, 0,
                             'skip_next changed unexpectedly for "canfinish" unavailable reviewer')
            self.assertEqual(self.reviewer_settings_for(canfinish_reviewer_no_review).skip_next, 0,
                             'skip_next changed unexpectedly for "canfinish" unavailable reviewer with no review')
            self.assertEqual(self.reviewer_settings_for(canfinish_reviewer_no_completed).skip_next, 0,
                             'skip_next changed unexpectedly for "canfinish" unavailable reviewer with no completed review')
            self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0,
                             'skip_next changed unexpectedly for assigned reviewer')

        def test_assign_reviewer_ignores_skip_next_when_canfinish_this_doc(self):
            """Should not update skip_next when 'canfinish' set for prior reviewer of current req
            
            If a reviewer is unavailable but 'canfinish' and has previously completed a review of this
            doc, they are a candidate to be assigned to it. In that case, when skip_next == 0, skipping
            over them means the assignment was not 'in order' and skip_next should not be updated. 
            """
            completed_req = ReviewRequestFactory(team=self.team, state_id='assigned')
            new_req = ReviewRequestFactory(team=self.team, doc=completed_req.doc)

            reviewer_to_skip = self.append_reviewer()
            settings = self.reviewer_settings_for(reviewer_to_skip)
            settings.skip_next = 1
            settings.save()

            canfinish_reviewer = self.append_reviewer()
            UnavailablePeriod.objects.create(
                team=self.team,
                person=canfinish_reviewer,
                start_date='2000-01-01',
                availability='canfinish',
            )
            self.create_old_review_assignment(
                reviewer=canfinish_reviewer,
                review_request=completed_req,
                state_id='completed',
            )

            reviewer_to_assign = self.append_reviewer()

            self.assertEqual(self.policy.default_reviewer_rotation_list(), 
                             [reviewer_to_skip, canfinish_reviewer, reviewer_to_assign],
                             'Test logic error - reviewers not in expected starting order')

            # assign the review
            self.policy.assign_reviewer(new_req, reviewer_to_assign.email(), add_skip=False)

            # Check results
            self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 1,
                             'skip_next changed unexpectedly for skipped reviewer')
            self.assertEqual(self.reviewer_settings_for(canfinish_reviewer).skip_next, 0,
                             'skip_next changed unexpectedly for "canfinish" reviewer')
            self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0,
                             'skip_next changed unexpectedly for assigned reviewer')

        def set_up_default_reviewer_rotation_list_test(self):
            """Helper to set up for the test_default_reviewer_rotation_list test and related tests"""
            for i in range(5):
                self.append_reviewer()

            # This reviewer should never be included.
            unavailable_reviewer = self.append_reviewer()
            UnavailablePeriod.objects.create(
                team=self.team,
                person=unavailable_reviewer,
                start_date='2000-01-01',
                availability='unavailable',
            )
            # This should not have any impact. Canfinish unavailable reviewers are included in
            # the default rotation, and filtered further when making assignment choices.
            UnavailablePeriod.objects.create(
                team=self.team,
                person=self.reviewers[1],
                start_date='2000-01-01',
                availability='canfinish',
            )
            return (
                [r for r in self.reviewers if r is not unavailable_reviewer], # available reviewers
                unavailable_reviewer,
            )
            
        def test_default_reviewer_rotation_list(self):
            available_reviewers, unavailable_reviewer = self.set_up_default_reviewer_rotation_list_test()
            rotation = self.policy.default_reviewer_rotation_list()
            self.assertNotIn(unavailable_reviewer, rotation)
            self.assertEqual(rotation, available_reviewers)
    
        def test_recommended_assignment_order(self):
            reviewer_low = self.append_reviewer()
            reviewer_high = self.append_reviewer()
    
            # reviewer_high appears later in the default rotation, but reviewer_low is the author
            doc = WgDraftFactory(group__acronym='mars', rev='01', authors=[reviewer_low])
            review_req = ReviewRequestFactory(doc=doc, team=self.team, type_id='early')
    
            order = self.policy.recommended_assignment_order(Email.objects.all(), review_req)
            self.assertEqual(order[0][0], str(reviewer_high.email()))
            self.assertEqual(order[1][0], str(reviewer_low.email()))
            self.assertIn('{}: #2'.format(reviewer_high.name), order[0][1])
            self.assertIn('{}: is author of document; #1'.format(reviewer_low.name), order[1][1])
    
            with self.assertRaises(ValueError):
                review_req_other_team = ReviewRequestFactory(doc=doc, type_id='early')
                self.policy.recommended_assignment_order(Email.objects.all(), review_req_other_team)
        
        def test_setup_reviewer_field(self):
            review_req = ReviewRequestFactory(team=self.team, type_id='early')
            
            reviewer = self.append_reviewer()

            partial_reviewer = self.append_reviewer()
            ReviewAssignmentFactory(review_request=review_req,
                                    reviewer=partial_reviewer.email(),
                                    state_id='part-completed')
            
            rejected_reviewer = self.append_reviewer()
            ReviewAssignmentFactory(review_request=ReviewRequestFactory(team=self.team,
                                                                        type_id='early',
                                                                        doc=review_req.doc),
                                    reviewer=rejected_reviewer.email(),
                                    state_id='rejected')
            
            no_response_reviewer = self.append_reviewer()
            ReviewAssignmentFactory(review_request=ReviewRequestFactory(team=self.team,
                                                                        type_id='early',
                                                                        doc=review_req.doc),
                                    reviewer=no_response_reviewer.email(),
                                    state_id='no-response')

            field = PersonEmailChoiceField(label="Assign Reviewer", empty_label="(None)", required=False)
            self.policy.setup_reviewer_field(field, review_req)
            
            addresses = list( map( lambda choice: choice[0], field.choices ) )
            
            self.assertNotIn(
                str(rejected_reviewer.email()), addresses,
                "Reviews should not suggest people who have rejected this request in the past")
            self.assertNotIn(
                str(no_response_reviewer.email()), addresses,
                "Reviews should not suggest people who have not responded to this request in the past.")
            
            self.assertEqual(field.initial, str(partial_reviewer.email()))

            self.assertEqual(field.choices[0], ('', '(None)'))
            self.assertEqual(field.choices[1][0], str(reviewer.email()))
            self.assertEqual(field.choices[2][0], str(partial_reviewer.email()))
            self.assertIn('{}: #1'.format(reviewer.name), field.choices[1][1])
            self.assertIn('{}: #2'.format(partial_reviewer.name), field.choices[2][1])
            self.assertIn('1 partially complete', field.choices[2][1])
            
        

class RotateAlphabeticallyReviewerQueuePolicyTest(_Wrapper.ReviewerQueuePolicyTestCase):
    reviewer_queue_policy_id = 'RotateAlphabetically'

    def test_default_reviewer_rotation_list_with_nextreviewerinteam(self):
        available_reviewers, _ = self.set_up_default_reviewer_rotation_list_test()
        assert(len(available_reviewers) > 4)

        # Policy with a current NextReviewerInTeam
        NextReviewerInTeam.objects.create(team=self.team, next_reviewer=available_reviewers[3])
        rotation = self.policy.default_reviewer_rotation_list()
        self.assertEqual(rotation, available_reviewers[3:] + available_reviewers[:3])

        # Policy with a NextReviewerInTeam that has left the team.
        Role.objects.get(person=available_reviewers[1]).delete()
        NextReviewerInTeam.objects.filter(team=self.team).update(next_reviewer=available_reviewers[1])
        rotation = self.policy.default_reviewer_rotation_list()
        self.assertEqual(rotation, available_reviewers[2:] + available_reviewers[:1])

    def test_return_reviewer_to_rotation_top(self):
        reviewer = self.append_reviewer()
        self.policy.return_reviewer_to_rotation_top(reviewer)
        self.assertTrue(ReviewerSettings.objects.get(person=reviewer).request_assignment_next)

    def test_update_policy_state_for_assignment(self):
        # make a bunch of reviewers
        review_req = ReviewRequestFactory(team=self.team)
        for i in range(5):
            self.append_reviewer()
        reviewers = self.reviewers

        self.assertEqual(reviewers, self.policy.default_reviewer_rotation_list())

        def get_skip_next(person):
            return self.reviewer_settings_for(person).skip_next

        # Regular in-order assignment without skips
        reviewer0_settings = self.reviewer_settings_for(reviewers[0])
        reviewer0_settings.request_assignment_next = True
        reviewer0_settings.save()
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[0], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=self.team).next_reviewer, reviewers[1])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 0)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)
        # request_assignment_next should be reset after any assignment
        self.assertFalse(self.reviewer_settings_for(reviewers[0]).request_assignment_next)

        # In-order assignment with add_skip
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[1], add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=self.team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)  # from current add_skip=True
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 0)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # In-order assignment to 2, but 3 has a skip_next, so 4 should be assigned.
        # 3 has skip_next decreased as it is skipped over, 1 retains its skip_next
        reviewer3_settings = self.reviewer_settings_for(reviewers[3])
        reviewer3_settings.skip_next = 2
        reviewer3_settings.save()
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[2], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=self.team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 0)
        self.assertEqual(get_skip_next(reviewers[1]), 1)  # from previous add_skip=true
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)  # from manually set skip_next - 1
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # Out of order assignments, nothing should change,
        # except the add_skip=True should still apply
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[3], add_skip=False)
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[2], add_skip=False)
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[1], add_skip=False)
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[0], add_skip=True)
        self.assertEqual(NextReviewerInTeam.objects.get(team=self.team).next_reviewer, reviewers[4])
        self.assertEqual(get_skip_next(reviewers[0]), 1)  # from current add_skip=True
        self.assertEqual(get_skip_next(reviewers[1]), 1)
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # Regular assignment, testing wrap-around
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[4], add_skip=False)
        self.assertEqual(NextReviewerInTeam.objects.get(team=self.team).next_reviewer, reviewers[2])
        self.assertEqual(get_skip_next(reviewers[0]), 0)  # skipped over with this assignment
        self.assertEqual(get_skip_next(reviewers[1]), 0)  # skipped over with this assignment
        self.assertEqual(get_skip_next(reviewers[2]), 0)
        self.assertEqual(get_skip_next(reviewers[3]), 1)
        self.assertEqual(get_skip_next(reviewers[4]), 0)

        # Leave only a single reviewer remaining, which should not trigger an infinite loop.
        # The deletion also causes NextReviewerInTeam to be deleted.
        [reviewer.delete() for reviewer in reviewers[1:]]
        self.assertEqual([reviewers[0]], self.policy.default_reviewer_rotation_list())
        self.policy.update_policy_state_for_assignment(review_req, assignee_person=reviewers[0], add_skip=False)
        # No NextReviewerInTeam should be created, the only possible next is the excluded assignee.
        self.assertFalse(NextReviewerInTeam.objects.filter(team=self.team))
        self.assertEqual([reviewers[0]], self.policy.default_reviewer_rotation_list())

    def test_assign_reviewer_updates_skip_next_without_add_skip(self):
        """Skipping reviewers with add_skip=False should update skip_counts properly"""
        review_req = ReviewRequestFactory(team=self.team)
        reviewer_to_skip = self.append_reviewer(skip_count=1)
        reviewer_to_assign = self.append_reviewer(skip_count=0)
        reviewer_to_skip_later = self.append_reviewer(skip_count=1)

        # Check test assumptions
        self.assertEqual(
            self.policy.default_reviewer_rotation_list(),
            [reviewer_to_skip, reviewer_to_assign, reviewer_to_skip_later],
        )

        self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=False)

        # Check results
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                         'skip_next not updated for skipped reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0,
                         'skip_next changed unexpectedly for assigned reviewer')
        # Expect to skip the later reviewer when updating NextReviewerInTeam
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip_later).skip_next, 0,
                         'skip_next not updated for reviewer to skip later')

    def test_assign_reviewer_updates_skip_next_with_add_skip(self):
        """Skipping reviewers with add_skip=True should update skip_counts properly"""
        review_req = ReviewRequestFactory(team=self.team)
        reviewer_to_skip = self.append_reviewer(skip_count=1)
        reviewer_to_assign = self.append_reviewer(skip_count=0)
        reviewer_to_skip_later = self.append_reviewer(skip_count=1)

        # Check test assumptions
        self.assertEqual(
            self.policy.default_reviewer_rotation_list(),
            [reviewer_to_skip, reviewer_to_assign, reviewer_to_skip_later],
        )

        self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=True)

        # Check results
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                         'skip_next not updated for skipped reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 1,
                         'skip_next not updated for assigned reviewer')
        # Expect to skip the later reviewer when updating NextReviewerInTeam
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip_later).skip_next, 0,
                         'skip_next not updated for reviewer to skip later')


class LeastRecentlyUsedReviewerQueuePolicyTest(_Wrapper.ReviewerQueuePolicyTestCase):
    """
    These tests only cover where this policy deviates from
    RotateAlphabeticallyReviewerQueuePolicy - the common behaviour
    inherited from AbstractReviewerQueuePolicy is covered in
    RotateAlphabeticallyReviewerQueuePolicyTest.
    """
    reviewer_queue_policy_id = 'LeastRecentlyUsed'

    def setUp(self):
        super(LeastRecentlyUsedReviewerQueuePolicyTest, self).setUp()
        self.last_assigned_on = timezone.now() - datetime.timedelta(days=365)
        
    def append_reviewer(self, skip_count=None):
        """Create a reviewer who will appear in the assignee options list
        
        New reviewer will be last in the default reviewer rotation list.
        """
        reviewer = super(LeastRecentlyUsedReviewerQueuePolicyTest, self).append_reviewer(skip_count)
        self.create_reviewer_assignment(reviewer)
        return reviewer

    def create_reviewer_assignment(self, reviewer):
        """Assign reviewer as most recent assignee
        
        Calling this will move a reviewer to the end of the LRU order.
        """
        if self.last_assigned_on is None:
            assignment = ReviewAssignmentFactory(review_request__team=self.team, reviewer=reviewer.email())
        else:
            assignment = ReviewAssignmentFactory(
                review_request__team=self.team,
                reviewer=reviewer.email(),
                assigned_on=self.last_assigned_on + datetime.timedelta(days=1)
            )
        self.last_assigned_on = assignment.assigned_on
        return assignment

    def create_old_review_assignment(self, reviewer, **kwargs):
        """Create a review that won't disturb the ordering of reviewers"""
        # Make a review older than our oldest review
        assert('assigned_on' not in kwargs)
        kwargs['assigned_on'] = timezone.now() - datetime.timedelta(days=400)
        return super(LeastRecentlyUsedReviewerQueuePolicyTest, self).create_old_review_assignment(reviewer, **kwargs)

    def test_default_reviewer_rotation_list_uses_latest_assignment(self):
        available_reviewers, _ = self.set_up_default_reviewer_rotation_list_test()
        assert(len(available_reviewers) > 2)  # need enough to avoid wrapping around in a way that invalidates tests
        
        # Give the first reviewer, who would normally appear at the top of the list, a newer assignment
        first_reviewer = available_reviewers[0]
        self.create_reviewer_assignment(first_reviewer)  # creates a new assignment, later assigned_on than all others

        self.assertEqual(self.policy.default_reviewer_rotation_list(), available_reviewers[1:] + [first_reviewer])

    def test_default_reviewer_rotation_list_ignores_rejected(self):
        available_reviewers, _ = self.set_up_default_reviewer_rotation_list_test()
        assert(len(available_reviewers) > 2)  # need enough to avoid wrapping around in a way that invalidates tests

        first_reviewer = available_reviewers[0]
        rejected_assignment = self.create_reviewer_assignment(first_reviewer)  # assigned_on later than all others...
        rejected_assignment.state_id = 'rejected'  #... but marked as rejected
        rejected_assignment.save()

        self.assertEqual(self.policy.default_reviewer_rotation_list(), available_reviewers)  # order unchanged

    def test_default_review_rotation_list_uses_assigned_on_date(self):
        available_reviewers, _ = self.set_up_default_reviewer_rotation_list_test()
        assert(len(available_reviewers) > 2)  # need enough to avoid wrapping around in a way that invalidates tests

        first_reviewer, second_reviewer = available_reviewers[:2]
        completed_assignment = self.create_reviewer_assignment(first_reviewer)  # moves to the end...
        second_reviewer_assignment = self.create_reviewer_assignment(second_reviewer)  # moves to the end...
        
        # Mark first_reviewer's assignment as completed after second_reviewer's was assigned
        completed_assignment.state_id = 'completed'
        completed_assignment.completed_on = second_reviewer_assignment.assigned_on + datetime.timedelta(days=1) 
        completed_assignment.save()

        # The completed_on timestamp should not have changed the order - second_reviewer still at the end        
        self.assertEqual(self.policy.default_reviewer_rotation_list(),
                         available_reviewers[2:] + [first_reviewer, second_reviewer])

    def test_return_reviewer_to_rotation_top(self):
        # Should do nothing, this is implicit in this policy, no state change is needed.
        self.policy.return_reviewer_to_rotation_top(self.append_reviewer())

    def test_assign_reviewer_updates_skip_next_without_add_skip(self):
        """Skipping reviewers with add_skip=False should update skip_counts properly"""
        review_req = ReviewRequestFactory(team=self.team)
        reviewer_to_skip = self.append_reviewer(skip_count=1)
        reviewer_to_assign = self.append_reviewer(skip_count=0)
        reviewer_to_skip_later = self.append_reviewer(skip_count=1)

        # Check test assumptions
        self.assertEqual(
            self.policy.default_reviewer_rotation_list(),
            [reviewer_to_skip, reviewer_to_assign, reviewer_to_skip_later],
        )

        self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=False)

        # Check results
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                         'skip_next not updated for skipped reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 0,
                         'skip_next changed unexpectedly for assigned reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip_later).skip_next, 1,
                         'skip_next changed unexpectedly for reviewer to skip later')

    def test_assign_reviewer_updates_skip_next_with_add_skip(self):
        """Skipping reviewers with add_skip=True should update skip_counts properly"""
        review_req = ReviewRequestFactory(team=self.team)
        reviewer_to_skip = self.append_reviewer(skip_count=1)
        reviewer_to_assign = self.append_reviewer(skip_count=0)
        reviewer_to_skip_later = self.append_reviewer(skip_count=1)

        # Check test assumptions
        self.assertEqual(
            self.policy.default_reviewer_rotation_list(),
            [reviewer_to_skip, reviewer_to_assign, reviewer_to_skip_later],
        )

        self.policy.assign_reviewer(review_req, reviewer_to_assign.email(), add_skip=True)

        # Check results
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip).skip_next, 0,
                         'skip_next not updated for skipped reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_assign).skip_next, 1,
                         'skip_next not updated for assigned reviewer')
        self.assertEqual(self.reviewer_settings_for(reviewer_to_skip_later).skip_next, 1,
                         'skip_next changed unexpectedly for reviewer to skip later')


class AssignmentOrderResolverTests(TestCase):
    def test_determine_ranking(self):
        # reviewer_high is second in the default rotation, reviewer_low is first
        # however, reviewer_high hits every score increase, reviewer_low hits every score decrease
        team = ReviewTeamFactory(acronym="rotationteam", name="Review Team", list_email="rotationteam@ietf.org", parent=Group.objects.get(acronym="farfut"))
        reviewer_high = create_person(team, "reviewer", name="Test Reviewer-high", username="testreviewerhigh")
        reviewer_low = create_person(team, "reviewer", name="Test Reviewer-low", username="testreviewerlow")
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
        rotation_list = [reviewer_low, reviewer_high]

        order = AssignmentOrderResolver(Email.objects.all(), review_req, rotation_list)
        ranking = order.determine_ranking()
        self.assertEqual(len(ranking), 2)
        self.assertEqual(ranking[0]['email'], reviewer_high.email())
        self.assertEqual(ranking[1]['email'], reviewer_low.email())
        # These scores follow the ordering of https://trac.ietf.org/trac/ietfdb/wiki/ReviewerQueuePolicy,
        self.assertEqual(ranking[0]['scores'], [ 1,  1,  1,  1,  1,  1,   0,  0, -1])
        self.assertEqual(ranking[1]['scores'], [-1, -1, -1, -1, -1, -1, -91, -2,  0])
        self.assertEqual(ranking[0]['label'], 'Test Reviewer-high: unavailable indefinitely (Can do follow-ups); requested to be selected next for assignment; reviewed document before; wishes to review document; #2; 1 no response, 1 partially complete, 1 fully completed')
        self.assertEqual(ranking[1]['label'], 'Test Reviewer-low: rejected review of document before; is author of document; filter regexp matches; max frequency exceeded, ready in 91 days; skip next 2; #1; currently 1 open, 10 pages')
