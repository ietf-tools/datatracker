# Copyright The IETF Trust 2022, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from ietf.submit.models import Submission
from ietf.submit import utils
from ietf.utils import log


@shared_task
def process_uploaded_submission(submission_id):
    submission = Submission.objects.get(pk=submission_id)
    utils.process_uploaded_submission(submission)


@shared_task(bind=True)
def poke(self):
    log.log(f'Poked {self.name}, request id {self.request.id}')
