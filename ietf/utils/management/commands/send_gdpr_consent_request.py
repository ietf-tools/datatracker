# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import debug                            # pyflakes:ignore

from ietf.person.models import Person, PersonEvent
from ietf.utils.mail import send_mail

class Command(BaseCommand):
    help = ("""
        Send GDPR consent request emails to persons who have not indicated consent
        to having their personal information stored.  Each send is logged as a
        PersonEvent.

        By default email sending happens at a rate of 1 message per second; the
        rate can be adjusted with the -r option.  At the start of a run, an estimate
        is given of how many persons to send to, and  how long the run will take.

        By default, emails are not sent out if there is less than 6 days since the
        previous consent request email.  The interval can be adjusted with the -m
        option.  One effect of this is that it is possible to break of a run and
        re-start it with for instance a different rate, without having duplicate
        messages go out to persons that were handled in the interrupted run.
        """)

    def add_arguments(self, parser):
        parser.add_argument('-n', '--dry-run', action='store_true', default=False,
            help="Don't send email, just list recipients")
        parser.add_argument('-d', '--date', help="Date of deletion (mentioned in message)")
        parser.add_argument('-m', '--minimum-interval', type=int, default=6,
            help="Minimum interval between re-sending email messages, default: %(default)s days")
        parser.add_argument('-r', '--rate', type=float, default=1.0,
            help='Rate of sending mail, default: %(default)s/s')
        parser.add_argument('-R', '--reminder', action='store_true', default=False,
            help='Preface the subject with "Reminder:"')
        parser.add_argument('user', nargs='*')
         

    def handle(self, *args, **options):
        # Don't send copies of the whole bulk mailing to the debug mailbox
        if settings.SERVER_MODE == 'production':
            settings.EMAIL_COPY_TO = "Email Debug Copy <outbound@ietf.org>"
        #
        event_type = 'gdpr_notice_email'
        # Arguments
        # --date
        if 'date' in options and options['date'] != None:
            try:
                date = datetime.datetime.strptime(options['date'], "%Y-%m-%d").date()
            except ValueError as e:
                raise CommandError('%s' % e)
        else:
            date = datetime.date.today() + datetime.timedelta(days=30)
        days = (date - datetime.date.today()).days
        if days <= 1:
            raise CommandError('date must be more than 1 day in the future')
        # --rate
        delay = 1.0/options['rate']
        # --minimum_interval
        minimum_interval = options['minimum_interval']
        latest_previous = datetime.datetime.now() - datetime.timedelta(days=minimum_interval)
        # user
        self.stdout.write('Querying the database for matching person records ...')
        if 'user' in options and options['user']:
            persons = Person.objects.filter(user__username__in=options['user'])
        else:
            exclude = PersonEvent.objects.filter(time__gt=latest_previous, type=event_type)
            persons = Person.objects.exclude(consent=True).exclude(personevent__in=exclude)
        # Report the size of the run
        runtime = persons.count() * delay
        self.stdout.write('Sending to %d users; estimated time a bit more than %d:%02d hours' % (persons.count(), runtime//3600, runtime%3600//60))
        subject='Personal Information in the IETF Datatracker'
        if options['reminder']:
            subject = "Reminder: " + subject
        for person in persons:
            fields = ', '.join(person.needs_consent())
            if fields and person.email_set.exists():
                if options['dry_run']:
                    print(("%-32s %-32s %-32s %-32s %s" % (person.email(), person.name_from_draft or '', person.name, person.ascii, fields)).encode('utf8'))
                else:
                    to = [ e.address for e in person.email_set.filter(active=True) ] # pyflakes:ignore
                    if not to:
                        to = [ e.address for e in person.email_set.all() ] # pyflakes:ignore
                    self.stdout.write("Sendimg email to %s" % to)
                    send_mail(None, to, "<gdprnoreply@ietf.org>",
                        subject=subject,
                        template='utils/personal_information_notice.txt',
                        context={
                            'date': date, 'days': days, 'fields': fields,
                            'person': person, 'settings': settings,
                            },
                        )
                    PersonEvent.objects.create(person=person, type='gdpr_notice_email', 
                                               desc="Sent GDPR notice email to %s with confirmation deadline %s" % (to, date))
                    time.sleep(delay)
                
