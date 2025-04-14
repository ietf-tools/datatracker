# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from ietf.review.utils import (
    review_assignments_needing_reviewer_reminder,
    email_reviewer_reminder,
    review_assignments_needing_secretary_reminder,
    email_secretary_reminder,
    send_unavailability_period_ending_reminder,
    send_reminder_all_open_reviews,
    send_review_reminder_overdue_assignment,
    send_reminder_unconfirmed_assignments,
)
from ietf.utils.log import log
from ietf.utils.timezone import date_today, DEADLINE_TZINFO


@shared_task
def send_review_reminders_task():
    today = date_today(DEADLINE_TZINFO)

    for assignment in review_assignments_needing_reviewer_reminder(today):
        email_reviewer_reminder(assignment)
        log(
            "Emailed reminder to {} for review of {} in {} (req. id {})".format(
                assignment.reviewer.address,
                assignment.review_request.doc_id,
                assignment.review_request.team.acronym,
                assignment.review_request.pk,
            )
        )

    for assignment, secretary_role in review_assignments_needing_secretary_reminder(
        today
    ):
        email_secretary_reminder(assignment, secretary_role)
        review_req = assignment.review_request
        log(
            "Emailed reminder to {} for review of {} in {} (req. id {})".format(
                secretary_role.email.address,
                review_req.doc_id,
                review_req.team.acronym,
                review_req.pk,
            )
        )

    period_end_reminders_sent = send_unavailability_period_ending_reminder(today)
    for msg in period_end_reminders_sent:
        log(msg)

    overdue_reviews_reminders_sent = send_review_reminder_overdue_assignment(today)
    for msg in overdue_reviews_reminders_sent:
        log(msg)

    open_reviews_reminders_sent = send_reminder_all_open_reviews(today)
    for msg in open_reviews_reminders_sent:
        log(msg)

    unconfirmed_assignment_reminders_sent = send_reminder_unconfirmed_assignments(today)
    for msg in unconfirmed_assignment_reminders_sent:
        log(msg)
