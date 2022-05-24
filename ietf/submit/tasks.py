# Copyright The IETF Trust 2022, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from ietf.submit.models import Submission
from ietf.submit.utils import process_uploaded_submission
from ietf.utils import log


@shared_task
def process_uploaded_submission_task(submission_id):
    try:
        submission = Submission.objects.get(pk=submission_id)
    except Submission.DoesNotExist:
        log.log(f'process_uploaded_submission_task called for missing submission_id={submission_id}')
    else:
        process_uploaded_submission(submission)


@shared_task(bind=True)
def poke(self):
    log.log(f'Poked {self.name}, request id {self.request.id}')
