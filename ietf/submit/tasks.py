# Copyright The IETF Trust 2022, All Rights Reserved
#
# Celery task definitions
#
import inspect

from celery import shared_task
from typing import Optional

from django.db.models import Min
from django.conf import settings
from django.utils import timezone

from ietf.submit.models import Submission
from ietf.utils import log


def get_submission(submission_id) -> Optional[Submission]:
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist:
        caller_frame = inspect.stack()[1]
        log.log(f"{caller_frame.function} called for missing submission_id={submission_id}")
        submission = None
    return submission


@shared_task
def process_uploaded_submission_task(submission_id):
    # avoid circular imports with ietf.submit.utils
    from ietf.submit.utils import process_uploaded_submission
    submission = get_submission(submission_id)
    if submission is not None:
        process_uploaded_submission(submission)


@shared_task
def process_and_accept_uploaded_submission_task(submission_id):
    # avoid circular imports with ietf.submit.utils
    from ietf.submit.utils import process_and_accept_uploaded_submission
    submission = get_submission(submission_id)
    if submission is not None:
        process_and_accept_uploaded_submission(submission)


@shared_task
def cancel_stale_submissions():
    # avoid circular imports with ietf.submit.utils
    from ietf.submit.utils import cancel_submission, create_submission_event
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
    # avoid circular imports with ietf.submit.utils
    from ietf.submit.utils import run_all_yang_model_checks, populate_yang_model_dirs
    populate_yang_model_dirs()
    run_all_yang_model_checks()


@shared_task(
    autoretry_for=(FileNotFoundError,),
    retry_backoff=5,  # exponential backoff starting with 5 seconds
    retry_kwargs={"max_retries": 5},  # 5, 10, 20, 40, 80 second delays, then give up
    retry_jitter=True,  # jitter, using retry time as max for a random delay
)
def move_files_to_repository_task(submission_id):
    # avoid circular imports with ietf.submit.utils
    from ietf.submit.utils import move_files_to_repository
    submission = get_submission(submission_id)
    if submission is not None:
        move_files_to_repository(submission)


@shared_task(bind=True)
def poke(self):
    log.log(f'Poked {self.name}, request id {self.request.id}')
