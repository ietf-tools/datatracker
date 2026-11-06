# Copyright The IETF Trust 2026, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand, CommandError

from ietf.sync.tasks import DEFAULT_BIBXML_BATCH_SIZE, recreate_all_rfc_bibxml_task


class Command(BaseCommand):
    help = (
        "Recreate BibXML for all RFCs and the subseries (BCP/STD/FYI) that "
        "contain them. The work is dispatched to Celery workers in batches, "
        "so a running Celery worker is required for the files to be written."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BIBXML_BATCH_SIZE,
            help="Number of RFCs per batch (default: %(default)s).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")
        recreate_all_rfc_bibxml_task(batch_size=batch_size)
        self.stdout.write(
            f"Dispatched BibXML recreation for all RFCs in batches of {batch_size}."
        )
