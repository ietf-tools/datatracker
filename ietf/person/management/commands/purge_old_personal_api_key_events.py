# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, Min

from ietf.person.models import PersonApiKeyEvent


class Command(BaseCommand):
    help = 'Purge PersonApiKeyEvent instances older than KEEP_DAYS days'

    def add_arguments(self, parser):
        parser.add_argument('keep_days', type=int,
                            help='Delete events older than this many days')
        parser.add_argument('-n', '--dry-run', action='store_true', default=False,
                            help="Don't delete events, just show what would be done")

    def handle(self, *args, **options):
        keep_days = options['keep_days']
        dry_run = options['dry_run']

        def _format_count(count, unit='day'):
            return '{} {}{}'.format(count, unit, ('' if count == 1 else 's'))

        if keep_days < 0:
            raise CommandError('Negative keep_days not allowed ({} was specified)'.format(keep_days))

        if dry_run:
            self.stdout.write('Dry run requested, records will not be deleted\n')

        self.stdout.write('Finding events older than {}\n'.format(_format_count(keep_days)))
        self.stdout.flush()

        now = datetime.now()
        old_events = PersonApiKeyEvent.objects.filter(
            time__lt=now - timedelta(days=keep_days)
        )

        stats = old_events.aggregate(Min('time'), Max('time'))
        old_count = old_events.count()
        if old_count == 0:
            self.stdout.write('No events older than {} found\n'.format(_format_count(keep_days)))
            return

        oldest_date = stats['time__min']
        oldest_ago = now - oldest_date
        newest_date = stats['time__max']
        newest_ago = now - newest_date

        action_fmt = 'Would delete {}\n' if dry_run else 'Deleting {}\n'
        self.stdout.write(action_fmt.format(_format_count(old_count, 'event')))
        self.stdout.write('    Oldest at {} ({} ago)\n'.format(oldest_date, _format_count(oldest_ago.days)))
        self.stdout.write('    Most recent at {} ({} ago)\n'.format(newest_date, _format_count(newest_ago.days)))
        self.stdout.flush()

        if not dry_run:
            old_events.delete()
