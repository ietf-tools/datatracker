# Copyright The IETF Trust 2022, All Rights Reserved
#
# Celery task definitions
#
from celery import chain, shared_task
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string

from ietf.submit.models import Submission
from ietf.submit import utils
from ietf.utils import log


@shared_task
def apply_checker(checker_path, submission_id):
    try:
        checker_class = import_string(checker_path)
    except ImportError:
        # todo fail
        raise
    submission = Submission.objects.get(pk=submission_id)

    basename = Path(settings.IDSUBMIT_STAGING_PATH) / f'{submission.name}-{submission.rev}'
    utils.apply_checker(
        checker_class(),
        submission,
        {
            ext: basename.with_suffix(f'.{ext}')
            for ext in ['xml', 'txt', 'html']
        }
    )


@shared_task
def accept_submission(submission_id):
    submission = Submission.objects.get(pk=submission_id)
    errors = [c.message for c in submission.checks.filter(passed__isnull=False) if not c.passed]
    if errors:
        # utils.remove_submission_files(submission)
        Submission.objects.filter(pk=submission_id).update(state_id='cancel')
        return 'egad'
    else:
        utils.accept_submission(submission)
        return 'yippie'


def check_and_accept_submission(submission_id):
    checks = [
        apply_checker.si(checker_path, submission_id)
        for checker_path in settings.IDSUBMIT_CHECKER_CLASSES
    ]
    return chain(*checks, accept_submission.si(submission_id))


@shared_task
def process_uploaded_submission(submission_id):
    submission = Submission.objects.get(pk=submission_id)
    utils.process_uploaded_submission(submission)


@shared_task(bind=True)
def poke(self):
    log.log(f'Poked {self.name}, request id {self.request.id}')
