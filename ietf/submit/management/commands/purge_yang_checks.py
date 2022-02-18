# Copyright The IETF Trust 2022 All Rights Reserved

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import migrations

from ietf.submit.models import Submission, SubmissionCheck

class Command(BaseCommand):
    help = ("Remove all but the first and last yangchecks for each Submission")

    def handle(self, *args, **options):
        print("Identifying purgeable SubmissionChecks")
        keep = set()
        for submission in tqdm(Submission.objects.all()):
            qs = submission.checks.filter(checker="yang validation")
            if qs.count() == 0:
                continue
            qs = qs.order_by("time")
            keep.add(qs.first().pk)
            keep.add(qs.last().pk)
        keep.discard(None)
        print("Purging SubmissionChecks")
        print(
            SubmissionCheck.objects.filter(checker="yang validation")
            .exclude(pk__in=list(keep))
            .delete()
        )
