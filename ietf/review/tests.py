# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime

from ietf.group.factories import RoleFactory
from ietf.utils.mail import empty_outbox, get_payload_text, outbox
from ietf.utils.test_utils import TestCase, reload_db_objects
from .factories import ReviewAssignmentFactory, ReviewRequestFactory, ReviewerSettingsFactory
from .mailarch import hash_list_message_id
from .models import ReviewerSettings, ReviewSecretarySettings, ReviewTeamSettings, UnavailablePeriod
from .utils import (email_secretary_reminder, review_assignments_needing_secretary_reminder,
                    email_reviewer_reminder, review_assignments_needing_reviewer_reminder,
                    send_reminder_unconfirmed_assignments, send_review_reminder_overdue_assignment,
                    send_reminder_all_open_reviews, send_unavailability_period_ending_reminder)

class HashTest(TestCase):

    def test_hash_list_message_id(self):
        for list, msgid, hash in (
                ('ietf', '156182196167.12901.11966487185176024571@ietfa.amsl.com',  'lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                ('codesprints', 'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',       'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                ('xml2rfc', '3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org',  'g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (u'ietf', u'156182196167.12901.11966487185176024571@ietfa.amsl.com','lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (u'codesprints', u'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (u'xml2rfc', u'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org','g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (b'ietf', b'156182196167.12901.11966487185176024571@ietfa.amsl.com','lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (b'codesprints', b'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (b'xml2rfc', b'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org','g6DN4SxJGDrlSuKsubwb6rRSePU'),
            ):
            self.assertEqual(hash, hash_list_message_id(list, msgid))
            

class ReviewAssignmentTest(TestCase):
    def do_test_update_review_req_status(self, assignment_state, expected_state):
        review_req = ReviewRequestFactory(state_id='assigned')
        ReviewAssignmentFactory(review_request=review_req, state_id='part-completed')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = assignment_state
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, expected_state)

    def test_update_review_req_status(self):
        # Test change
        for assignment_state in ['no-response', 'rejected', 'withdrawn', 'overtaken']:
            self.do_test_update_review_req_status(assignment_state, 'requested')
        # Test no-change
        for assignment_state in ['accepted', 'assigned', 'completed', 'part-completed', 'unknown', ]:
            self.do_test_update_review_req_status(assignment_state, 'assigned')

    def test_no_update_review_req_status_when_other_active_assignment(self):
        # If there is another still active assignment, do not update review_req state
        review_req = ReviewRequestFactory(state_id='assigned')
        ReviewAssignmentFactory(review_request=review_req, state_id='assigned')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = 'no-response'
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, 'assigned')

    def test_no_update_review_req_status_when_review_req_withdrawn(self):
        # review_req state must only be changed to "requested", if old state was "assigned",
        # to prevent reviving dead review requests
        review_req = ReviewRequestFactory(state_id='withdrawn')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = 'no-response'
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, 'withdrawn')


class ReviewAssignmentReminderTests(TestCase):
    today = datetime.date.today()
    deadline = today + datetime.timedelta(days=6)

    def setUp(self):
        super().setUp()
        self.review_req = ReviewRequestFactory(
            state_id='assigned',
            deadline=self.deadline,
        )
        self.team = self.review_req.team
        self.reviewer = RoleFactory(
            name_id='reviewer',
            group=self.team,
            person__user__username='reviewer',
        ).person
        self.assignment = ReviewAssignmentFactory(
            review_request=self.review_req,
            state_id='assigned',
            assigned_on=self.review_req.time,
            reviewer=self.reviewer.email_set.first(),
        )

    def make_secretary(self, username, remind_days=None):
        secretary_role = RoleFactory(
            name_id='secr',
            group=self.team,
            person__user__username=username,
        )
        ReviewSecretarySettings.objects.create(
            team=self.team,
            person=secretary_role.person,
            remind_days_before_deadline=remind_days,
        )
        return secretary_role

    def make_non_secretary(self, username, remind_days=None):
        """Make a non-secretary role that has a ReviewSecretarySettings

        This is a little odd, but might come up if an ex-secretary takes on another role and still
        has a ReviewSecretarySettings record.
        """
        role = RoleFactory(
            name_id='reviewer',
            group=self.team,
            person__user__username=username,
        )
        ReviewSecretarySettings.objects.create(
            team=self.team,
            person=role.person,
            remind_days_before_deadline=remind_days,
        )
        return role

    def test_review_assignments_needing_secretary_reminder(self):
        """Notification sent to multiple secretaries"""
        # Set up two secretaries with the same remind_days one with a different, and one with None.
        secretary_roles = [
            self.make_secretary(username='reviewsecretary0', remind_days=6),
            self.make_secretary(username='reviewsecretary1', remind_days=6),
            self.make_secretary(username='reviewsecretary2', remind_days=5),
            self.make_secretary(username='reviewsecretary3', remind_days=None),  # never notified
        ]
        self.make_non_secretary(username='nonsecretary', remind_days=6)  # never notified

        # Check from more than remind_days before the deadline all the way through the day before.
        # Should only get reminders on the expected days.
        self.assertCountEqual(
            review_assignments_needing_secretary_reminder(self.deadline - datetime.timedelta(days=7)),
            [],
            'No reminder needed when deadline is more than remind_days away',
        )
        self.assertCountEqual(
            review_assignments_needing_secretary_reminder(self.deadline - datetime.timedelta(days=6)),
            [(self.assignment, secretary_roles[0]), (self.assignment, secretary_roles[1])],
            'Reminders needed for all secretaries when deadline is exactly remind_days away',
        )
        self.assertCountEqual(
            review_assignments_needing_secretary_reminder(self.deadline - datetime.timedelta(days=5)),
            [(self.assignment, secretary_roles[2])],
            'Reminder needed when deadline is exactly remind_days away',
        )
        for days in range(1, 5):
            self.assertCountEqual(
                review_assignments_needing_secretary_reminder(self.deadline - datetime.timedelta(days=days)),
                [],
                f'No reminder needed when deadline is less than remind_days away (tried {days})',
            )

    def test_email_secretary_reminder_emails_secretaries(self):
        """Secretary review assignment reminders are sent to secretaries"""
        secretary_role = self.make_secretary(username='reviewsecretary')
        # create a couple other roles for the team to check that only the requested secretary is reminded
        self.make_secretary(username='ignoredsecretary')
        self.make_non_secretary(username='nonsecretary')

        empty_outbox()
        email_secretary_reminder(self.assignment, secretary_role)
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        text = get_payload_text(msg)
        self.assertIn(secretary_role.email.address, msg['to'])
        self.assertIn(self.review_req.doc.name, msg['subject'])
        self.assertIn(self.review_req.doc.name, text)
        self.assertIn(self.team.acronym, msg['subject'])
        self.assertIn(self.team.acronym, text)

    def test_review_assignments_needing_reviewer_reminder(self):
        # method should find lists of assignments
        reviewer_settings = ReviewerSettings.objects.create(
            team=self.team,
            person=self.reviewer,
            remind_days_before_deadline=6,
        )

        # Give this reviewer another team with a review to be sure
        # we don't have cross-talk between teams.
        second_req = ReviewRequestFactory(state_id='assigned', deadline=self.deadline)
        second_team = second_req.team
        second_assignment = ReviewAssignmentFactory(
            review_request=second_req,
            state_id='assigned',
            assigned_on=second_req.time,
            reviewer=self.reviewer.email(),
        )
        ReviewerSettingsFactory(
            team=second_team,
            person=self.reviewer,
            remind_days_before_deadline=5,
        )

        self.assertCountEqual(
            review_assignments_needing_reviewer_reminder(self.deadline - datetime.timedelta(days=7)),
            [],
            'No reminder needed when deadline is more than remind_days away'
        )
        self.assertCountEqual(
            review_assignments_needing_reviewer_reminder(self.deadline - datetime.timedelta(days=6)),
            [self.assignment],
            'Reminder needed when deadline is exactly remind_days away',
        )
        self.assertCountEqual(
            review_assignments_needing_reviewer_reminder(self.deadline - datetime.timedelta(days=5)),
            [second_assignment],
            'Reminder needed for other assignment'
        )
        self.assertCountEqual(
            review_assignments_needing_reviewer_reminder(self.deadline - datetime.timedelta(days=4)),
            [],
            'No reminder needed when deadline is less than remind_days away'
        )

        # should never send a reminder when disabled
        reviewer_settings.remind_days_before_deadline = None
        reviewer_settings.save()
        second_assignment.delete()  # get rid of this one for the second test

        # test over a range that includes when we *did* send a reminder above
        for days in range(1, 8):
            self.assertCountEqual(
                review_assignments_needing_reviewer_reminder(self.deadline - datetime.timedelta(days=days)),
                [],
                f'No reminder should be sent when reminders are disabled (sent for days={days})',
            )

    def test_email_review_reminder_emails_reviewers(self):
        """Reviewer assignment reminders are sent to the reviewers"""
        empty_outbox()
        email_reviewer_reminder(self.assignment)
        self.assertEqual(len(outbox), 1)
        msg = outbox[0]
        text = get_payload_text(msg)
        self.assertIn(self.reviewer.email_address(), msg['to'])
        self.assertIn(self.review_req.doc.name, msg['subject'])
        self.assertIn(self.review_req.doc.name, text)
        self.assertIn(self.team.acronym, msg['subject'])

    def test_send_reminder_unconfirmed_assignments(self):
        """Unconfirmed assignment reminders are sent to reviewer and team secretary"""
        assigned_on = self.assignment.assigned_on.date()
        secretaries = [
            self.make_secretary(username='reviewsecretary0').person,
            self.make_secretary(username='reviewsecretary1').person,
        ]

        # assignments that should be ignored (will result in extra emails being sent if not)
        ReviewAssignmentFactory(
            review_request=self.review_req,
            state_id='accepted',
            assigned_on=self.review_req.time,
        )
        ReviewAssignmentFactory(
            review_request=self.review_req,
            state_id='completed',
            assigned_on=self.review_req.time,
        )
        ReviewAssignmentFactory(
            review_request=self.review_req,
            state_id='rejected',
            assigned_on=self.review_req.time,
        )

        # Create a second review for a different team to test for cross-talk between teams.
        ReviewAssignmentFactory(
            state_id='completed',  # something that does not need a reminder
            reviewer=self.reviewer.email(),
        )

        # By default, these reminders are disabled for all teams.
        ReviewTeamSettings.objects.update(remind_days_unconfirmed_assignments=1)

        empty_outbox()
        log = send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=1))
        self.assertEqual(len(outbox), 1)
        self.assertIn(self.reviewer.email_address(), outbox[0]["To"])
        for secretary in secretaries:
            self.assertIn(
                secretary.email_address(),
                outbox[0]["Cc"],
                f'Secretary {secretary.user.username} was not copied on the reminder',
            )
        self.assertEqual(outbox[0]["Subject"], "Reminder: you have not responded to a review assignment")
        message = get_payload_text(outbox[0])
        self.assertIn(self.team.acronym, message)
        self.assertIn('accept or reject the assignment on', message)
        self.assertIn(self.review_req.doc.name, message)
        self.assertEqual(len(log), 1)
        self.assertIn(self.reviewer.email_address(), log[0])
        self.assertIn('not accepted/rejected review assignment', log[0])

    def test_send_reminder_unconfirmed_assignments_respects_remind_days(self):
        """Unconfirmed assignment reminders should respect the team settings"""
        assigned_on = self.assignment.assigned_on.date()

        # By default, these reminders are disabled for all teams.
        empty_outbox()
        for days in range(10):
            send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=days))
        self.assertEqual(len(outbox), 0)

        # expect a notification every day except the day of assignment
        ReviewTeamSettings.objects.update(remind_days_unconfirmed_assignments=1)
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=0))
        self.assertEqual(len(outbox), 0)  # no message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=1))
        self.assertEqual(len(outbox), 1)  # one new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=2))
        self.assertEqual(len(outbox), 2)  # one new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=3))
        self.assertEqual(len(outbox), 3)  # one new message

        # expect a notification every other day
        empty_outbox()
        ReviewTeamSettings.objects.update(remind_days_unconfirmed_assignments=2)
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=0))
        self.assertEqual(len(outbox), 0)  # no message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=1))
        self.assertEqual(len(outbox), 0)  # no message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=2))
        self.assertEqual(len(outbox), 1)  # one new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=3))
        self.assertEqual(len(outbox), 1)  # no new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=4))
        self.assertEqual(len(outbox), 2)  # one new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=5))
        self.assertEqual(len(outbox), 2)  # no new message
        send_reminder_unconfirmed_assignments(assigned_on + datetime.timedelta(days=6))
        self.assertEqual(len(outbox), 3)  # no new message

    def test_send_unavailability_period_ending_reminder(self):
        secretary = self.make_secretary(username='reviewsecretary')
        empty_outbox()
        today = datetime.date.today()
        UnavailablePeriod.objects.create(
            team=self.team,
            person=self.reviewer,
            start_date=today - datetime.timedelta(days=40),
            end_date=today + datetime.timedelta(days=3),
            availability="unavailable",
        )
        UnavailablePeriod.objects.create(
            team=self.team,
            person=self.reviewer,
            # This object should be ignored, length is too short
            start_date=today - datetime.timedelta(days=20),
            end_date=today + datetime.timedelta(days=3),
            availability="unavailable",
        )
        UnavailablePeriod.objects.create(
            team=self.team,
            person=self.reviewer,
            start_date=today - datetime.timedelta(days=40),
            # This object should be ignored, end date is too far away
            end_date=today + datetime.timedelta(days=4),
            availability="unavailable",
        )
        UnavailablePeriod.objects.create(
            team=self.team,
            person=self.reviewer,
            # This object should be ignored, end date is too close
            start_date=today - datetime.timedelta(days=40),
            end_date=today + datetime.timedelta(days=2),
            availability="unavailable",
        )
        log = send_unavailability_period_ending_reminder(today)

        self.assertEqual(len(outbox), 1)
        self.assertTrue(self.reviewer.email_address() in outbox[0]["To"])
        self.assertTrue(secretary.person.email_address() in outbox[0]["To"])
        message = get_payload_text(outbox[0])
        self.assertTrue(self.reviewer.name in message)
        self.assertTrue(self.team.acronym in message)
        self.assertEqual(len(log), 1)
        self.assertTrue(self.reviewer.name in log[0])
        self.assertTrue(self.team.acronym in log[0])

    def test_send_review_reminder_overdue_assignment(self):
        """An overdue assignment reminder should be sent to the secretary

        This tests that a second set of assignments for the same reviewer but a different
        review team does not cause cross-talk between teams. To do this, it removes the
        ReviewTeamSettings instance for the second review team. At the moment, this has
        the effect of disabling these reminders. This is a bit of a hack, because I'm not
        sure that review teams without the ReviewTeamSettings should exist. It has the
        needed effect but might require rethinking in the future.
        """
        secretary = self.make_secretary(username='reviewsecretary')

        # Set the remind_date to be exactly one grace period after self.deadline
        remind_date = self.deadline + datetime.timedelta(days=5)
        # Create a second request for a second team that will not be sent reminders
        second_team = ReviewAssignmentFactory(
            review_request__state_id='assigned',
            review_request__deadline=self.deadline,
            state_id='assigned',
            assigned_on=self.deadline,
            reviewer=self.reviewer.email_set.first(),
        ).review_request.team
        second_team.reviewteamsettings.delete()  # prevent it from being sent reminders

        # An assignment that is not yet overdue
        not_overdue = remind_date + datetime.timedelta(days=1)
        ReviewAssignmentFactory(
            review_request__team=self.team,
            review_request__state_id='assigned',
            review_request__deadline=not_overdue,
            state_id='assigned',
            assigned_on=not_overdue,
            reviewer=self.reviewer.email_set.first(),
        )
        ReviewAssignmentFactory(
            review_request__team=second_team,
            review_request__state_id='assigned',
            review_request__deadline=not_overdue,
            state_id='assigned',
            assigned_on=not_overdue,
            reviewer=self.reviewer.email_set.first(),
        )

        # An assignment that is overdue but is not past the grace period
        in_grace_period = remind_date - datetime.timedelta(days=1)
        ReviewAssignmentFactory(
            review_request__team=self.team,
            review_request__state_id='assigned',
            review_request__deadline=in_grace_period,
            state_id='assigned',
            assigned_on=in_grace_period,
            reviewer=self.reviewer.email_set.first(),
        )
        ReviewAssignmentFactory(
            review_request__team=second_team,
            review_request__state_id='assigned',
            review_request__deadline=in_grace_period,
            state_id='assigned',
            assigned_on=in_grace_period,
            reviewer=self.reviewer.email_set.first(),
        )

        empty_outbox()
        log = send_review_reminder_overdue_assignment(remind_date)
        self.assertEqual(len(log), 1)

        self.assertEqual(len(outbox), 1)
        self.assertTrue(secretary.person.email_address() in outbox[0]["To"])
        self.assertEqual(outbox[0]["Subject"], "1 Overdue review for team {}".format(self.team.acronym))
        message = get_payload_text(outbox[0])
        self.assertIn(
            self.team.acronym + ' has 1 accepted or assigned review overdue by at least 5 days.',
            message,
        )
        self.assertIn('Review of {} by {}'.format(self.review_req.doc.name, self.reviewer.plain_name()), message)
        self.assertEqual(len(log), 1)
        self.assertIn(secretary.person.email_address(), log[0])
        self.assertIn('1 overdue review', log[0])

    def test_send_reminder_all_open_reviews(self):
        self.make_secretary(username='reviewsecretary')
        ReviewerSettingsFactory(team=self.team, person=self.reviewer, remind_days_open_reviews=1)

        # Create another assignment for this reviewer in a different team.
        # Configure so that a reminder should not be sent for the date we test. It should not
        # be included in the reminder that's sent - only one open review assignment should be
        # reported.
        second_req = ReviewRequestFactory(state_id='assigned', deadline=self.deadline)
        second_team = second_req.team
        ReviewAssignmentFactory(
            review_request=second_req,
            state_id='assigned',
            assigned_on=second_req.time,
            reviewer=self.reviewer.email(),
        )
        ReviewerSettingsFactory(team=second_team, person=self.reviewer, remind_days_open_reviews=13)

        empty_outbox()
        today = datetime.date.today()
        log = send_reminder_all_open_reviews(today)

        self.assertEqual(len(outbox), 1)
        self.assertTrue(self.reviewer.email_address() in outbox[0]["To"])
        self.assertEqual(outbox[0]["Subject"], "Reminder: you have 1 open review assignment")
        message = get_payload_text(outbox[0])
        self.assertTrue(self.team.acronym in message)
        self.assertTrue('you have 1 open review' in message)
        self.assertTrue(self.review_req.doc.name in message)
        self.assertTrue(self.review_req.deadline.strftime('%Y-%m-%d') in message)
        self.assertEqual(len(log), 1)
        self.assertTrue(self.reviewer.email_address() in log[0])
        self.assertTrue('1 open review' in log[0])

