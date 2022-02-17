# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime

from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ietf.meeting.models import Session
from ietf.utils.meetecho import ConferenceManager, MeetechoAPIError


class Command(BaseCommand):
    help = 'Manage Meetecho conferences'
    
    def add_arguments(self, parser) -> None:
        parser.add_argument('group', type=str)
        parser.add_argument('-d', '--delete', type=int, action='append',
                            metavar='SESSION_PK',
                            help='Delete the conference associated with the specified Session')
    
    def handle(self, group, delete, *args, **options):
        conf_mgr = ConferenceManager(settings.MEETECHO_API_CONFIG)
        if delete:
            self.handle_delete_conferences(conf_mgr, group, delete)
        else:
            self.handle_list_conferences(conf_mgr, group)

    def handle_list_conferences(self, conf_mgr, group):
        confs, conf_sessions = self.fetch_conferences(conf_mgr, group)
        self.stdout.write(f'Meetecho conferences for {group}:\n\n')
        for conf in confs:
            sessions_desc = ', '.join(str(s.pk) for s in conf_sessions[conf.id]) or None
            self.stdout.write(
                dedent(f'''\
                * {conf.description}
                    Start time: {conf.start_time} 
                    Duration: {int(conf.duration.total_seconds() // 60)} minutes
                    URL: {conf.url}
                    Associated session PKs: {sessions_desc}
                
                ''')
            )

    def handle_delete_conferences(self, conf_mgr, group, session_pks_to_delete):
        sessions_to_delete = Session.objects.filter(pk__in=session_pks_to_delete)
        confs, conf_sessions = self.fetch_conferences(conf_mgr, group)
        confs_to_delete = []
        descriptions = []
        for session in sessions_to_delete:
            for conf in confs:
                associated = conf_sessions[conf.id]
                if session in associated:
                    confs_to_delete.append(conf)
                    sessions_desc = ', '.join(str(s.pk) for s in associated) or None
                    descriptions.append(
                        f'{conf.description} ({conf.start_time}, {int(conf.duration.total_seconds() // 60)} mins) - used by {sessions_desc}'
                    )
        if len(confs_to_delete) > 0:
            self.stdout.write('Will delete:')
            for desc in descriptions:
                self.stdout.write(f'* {desc}')

            try:
                proceed = input('Proceed [y/N]? ').lower()
            except EOFError:
                proceed = 'n'
            if proceed in ['y', 'yes']:
                for conf, desc in zip(confs_to_delete, descriptions):
                    conf.delete()
                    self.stdout.write(f'Deleted {desc}')
            else:
                self.stdout.write('Nothing deleted.')
        else:
            self.stdout.write('No associated Meetecho conferences found')

    def fetch_conferences(self, conf_mgr, group):
        try:
            confs = conf_mgr.fetch(group)
        except MeetechoAPIError as err:
            raise CommandError('API error fetching Meetecho conference data') from err

        conf_sessions = {}
        for conf in confs:
            conf_sessions[conf.id] = Session.objects.filter(
                group__acronym=group,
                meeting__date__gte=datetime.date.today(),
                remote_instructions__contains=conf.url,
            )
        return confs, conf_sessions
