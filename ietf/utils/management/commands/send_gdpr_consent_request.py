# Copyright The IETF Trust 2016, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import syslog
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.utils.mail import send_mail

def log(message):
    syslog.syslog(message)

class Command(BaseCommand):
    help = (u"Send GDPR consent requests to those that need it")

    def add_arguments(self, parser):
         parser.add_argument('-n', '--dry-run', dest='dryrun', action='store_true', default=False,
             help="Don't send email, just list recipients")

    def handle(self, *args, **options):
        for person in Person.objects.exclude(consent=True):
            fields = ', '.join(person.needs_consent())
            date = datetime.date.today() + datetime.timedelta(days=30)
            if fields and person.email_set.exists():
                if options['dryrun']:
                    print(("%-32s %-32s %-32s %-32s %s" % (person.email(), person.name_from_draft or '', person.name, person.ascii, fields)).encode('utf8'))
                else:
                    to = [ e.address for e in person.email_set.filter(active=True) ]
                    if not to:
                        to = [ e.address for e in person.email_set.all() ]
                    send_mail(None, to, None,
                        subject='Personal Information in the IETF Datatracker',
                        template='utils/personal_information_notice.txt',
                        context={'fields': fields, 'person': person, 'settings': settings, 'date': date, }, )

