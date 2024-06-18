# Copyright The IETF Trust 2022, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from django.db.models import Min
from django.conf import settings
from django.utils import timezone

from ietf.submit.models import Submission
from ietf.submit.utils import (cancel_submission, create_submission_event, process_uploaded_submission,
                               process_and_accept_uploaded_submission, run_all_yang_model_checks,
                               populate_yang_model_dirs)
from ietf.utils import log


@shared_task
def process_uploaded_submission_task(submission_id):
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist:
        log.log(f'process_uploaded_submission_task called for missing submission_id={submission_id}')
    else:
        process_uploaded_submission(submission)


@shared_task
def process_and_accept_uploaded_submission_task(submission_id):
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist:
        log.log(f'process_uploaded_submission_task called for missing submission_id={submission_id}')
    else:
        process_and_accept_uploaded_submission(submission)


@shared_task
def cancel_stale_submissions():
    now = timezone.now()
    # first check for submissions gone stale awaiting validation
    stale_unvalidated_submissions = Submission.objects.filter(
        state_id='validating',
    ).annotate(
        submitted_at=Min('submissionevent__time'),
    ).filter(
        submitted_at__lt=now - settings.IDSUBMIT_MAX_VALIDATION_TIME,
    )
    for subm in stale_unvalidated_submissions:
        age = now - subm.submitted_at
        log.log(f'Canceling stale submission (id={subm.id}, age={age})')
        cancel_submission(subm)
        create_submission_event(None, subm, 'Submission canceled: validation checks took too long')

    # now check for expired submissions
    expired_submissions = Submission.objects.exclude(
        state_id__in=["posted", "cancel"],
    ).annotate(
        submitted_at=Min("submissionevent__time"),
    ).filter(
        submitted_at__lt=now - settings.IDSUBMIT_EXPIRATION_AGE,
    )
    for subm in expired_submissions:
        age = now - subm.submitted_at
        log.log(f'Canceling expired submission (id={subm.id}, age={age})')
        cancel_submission(subm)
        create_submission_event(None, subm, 'Submission canceled: expired without being posted')


@shared_task
def run_yang_model_checks_task():
    populate_yang_model_dirs()
    run_all_yang_model_checks()

    
@shared_task(bind=True)
def poke(self):
    log.log(f'Poked {self.name}, request id {self.request.id}')
