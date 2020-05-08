# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime

from textwrap import dedent

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from request_profiler.models import ProfilingRecord

class Command(BaseCommand):
    """
    Purge information older than a given number of days (default 30) from the
    profiling records table
    """

    help = dedent(__doc__).strip()
            
            
    def add_arguments(self, parser):
        parser.add_argument('-d', '--days', dest='days', type=int, default=3,
            help='Purge records older than this (default %(default)s days).')

    def handle(self, *filenames, **options):
        start = datetime.datetime.now() - datetime.timedelta(days=int(options['days']))
        deleted = ProfilingRecord.objects.filter(start_ts__lt=start).delete()
        if options['verbosity'] > 1:
            self.stdout.write('deleted: %s' % str(deleted))
