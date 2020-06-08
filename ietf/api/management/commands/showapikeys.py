# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.person.models import PersonalApiKey

class Command(BaseCommand):

    help = 'Show existing personal API keys'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        format = "%-36s  %-24s  %-64s  %-16s"
        self.stdout.write(format % ('Endpoint', 'Login', 'Key', 'Used'))
        for key in PersonalApiKey.objects.filter():
            self.stdout.write(format % (key.endpoint, key.person.user.username, key.hash(), key.latest.strftime('%Y-%m-%d %H:%M') if key.latest else ''))
