# Copyright The IETF Trust 2014-2021, All Rights Reserved
# -*- coding: utf-8 -*-


from django.core.management.base import BaseCommand, CommandError

from ietf.ipr.utils import generate_draft_recursive_txt


class Command(BaseCommand):
    help = ("Generate machine-readable list of IPR disclosures by draft name (recursive)")

    def handle(self, *args, **options):
        try:
            generate_draft_recursive_txt()
        except (ValueError, IOError) as e:
            raise CommandError(e)
