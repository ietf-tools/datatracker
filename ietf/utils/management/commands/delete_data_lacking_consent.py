# Copyright The IETF Trust 2016, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import datetime
from tqdm import tqdm

from django.conf import settings
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import F

import debug                            # pyflakes:ignore

from ietf.community.models import SearchRule
from ietf.person.models import Person, Alias, PersonalApiKey, Email
from ietf.person.name import unidecode_name
from ietf.utils.log import log

class Command(BaseCommand):
    help = (u"""

        Delete data for which consent to store the data has not been given,
        where the data does not fall under the GDPR Legitimate Interest clause
        for the IETF.  This includes full name, ascii name, bio, login,
        notification subscriptions and email addresses that are not derived from
        published drafts or ietf roles.

        """)

    def add_arguments(self, parser):
         parser.add_argument('-n', '--dry-run', action='store_true', default=False,
             help="Don't delete anything, just list what would be done.")
#          parser.add_argument('-d', '--date', help="Date of deletion (mentioned in message)")
         parser.add_argument('-m', '--minimum-response-time', metavar='TIME', type=int, default=7,
             help="Minimum response time, default: %(default)s days.  Persons to whom a "
                  "consent request email has been sent more recently than this will not "
                  "be affected by the run.")
#          parser.add_argument('-r', '--rate', type=float, default=1.0,
#              help='Rate of sending mail, default: %(default)s/s')
#          parser.add_argument('user', nargs='*')
         

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        verbosity  = int(options['verbosity'])
        event_type = 'gdpr_notice_email'
        settings.DEBUG = False          # don't log to console

        # users
        users = User.objects.filter(person__isnull=True, username__contains='@')
        self.stdout.write("Found %d users without associated person records" % (users.count(), ))
        emails = Email.objects.filter(address__in=users.values_list('username', flat=True))
        # fix up users that don't have person records, but have a username matching a nown email record
        self.stdout.write("Checking usernames against email records ...")
        for email in tqdm(emails):
            user = users.get(username=email.address)
            if email.person.user_id:
                if dry_run:
                    self.stdout.write("Would delete user  #%-6s (%s) %s" % (user.id, user.last_login, user.username))
                else:
                    log("Deleting user #%-6s (%s) %s: no person record, matching email has other user" % (user.id, user.last_login, user.username))
                    user_id = user.id
                    user.delete()
                    Person.history.filter(user_id=user_id).delete()
                    Email.history.filter(history_user=user_id).delete()
            else:
                if dry_run:
                    self.stdout.write("Would connect user #%-6s %s to person #%-6s %s" % (user.id, user.username, email.person.id, email.person.ascii_name()))
                else:
                    log("Connecting user #%-6s %s to person #%-6s %s" % (user.id, user.username, email.person.id, email.person.ascii_name()))
                    email.person.user_id = user.id
                    email.person.save()
        # delete users without person records
        users = users.exclude(username__in=emails.values_list('address', flat=True))
        if dry_run:
            self.stdout.write("Would delete %d users without associated person records" % (users.count(), ))
        else:
            if users.count():
                log("Deleting %d users without associated person records" % (users.count(), ))
                assert not users.filter(person__isnull=False).exists()
                user_ids = users.values_list('id', flat=True)
                users.delete()
                assert not Person.history.filter(user_id__in=user_ids).exists()


        # persons
        self.stdout.write('Querying the database for person records without given consent ...')
        notification_cutoff = datetime.datetime.now() - datetime.timedelta(days=options['minimum_response_time'])
        persons = Person.objects.exclude(consent=True)
        persons = persons.exclude(id=1) # make sure we don't delete System ;-)
        self.stdout.write("Found %d persons with information for which we don't have consent." % (persons.count(), ))

        # Narrow to persons we don't have Legitimate Interest in, and delete those fully
        persons = persons.exclude(docevent__by=F('pk'))
        persons = persons.exclude(documentauthor__person=F('pk')).exclude(dochistoryauthor__person=F('pk'))
        persons = persons.exclude(email__liaisonstatement__from_contact__person=F('pk'))
        persons = persons.exclude(email__reviewrequest__reviewer__person=F('pk'))
        persons = persons.exclude(email__shepherd_dochistory_set__shepherd__person=F('pk'))
        persons = persons.exclude(email__shepherd_document_set__shepherd__person=F('pk'))
        persons = persons.exclude(iprevent__by=F('pk'))
        persons = persons.exclude(meetingregistration__person=F('pk'))
        persons = persons.exclude(message__by=F('pk'))
        persons = persons.exclude(name_from_draft='')
        persons = persons.exclude(personevent__time__gt=notification_cutoff, personevent__type=event_type)
        persons = persons.exclude(reviewrequest__requested_by=F('pk'))
        persons = persons.exclude(role__person=F('pk')).exclude(rolehistory__person=F('pk'))
        persons = persons.exclude(session__requested_by=F('pk'))
        persons = persons.exclude(submissionevent__by=F('pk'))
        self.stdout.write("Found %d persons with information for which we neither have consent nor legitimate interest." % (persons.count(), ))
        if persons.count() > 0:
            self.stdout.write("Deleting records for persons for which we have with neither consent nor legitimate interest ...")
            for person in (persons if dry_run else tqdm(persons)):
                if dry_run:
                    self.stdout.write(("Would delete record   #%-6d: (%s) %-32s %-48s" % (person.pk, person.time, person.ascii_name(), "<%s>"%person.email())).encode('utf8'))
                else:
                    if verbosity > 1:
                        # development aids
                        collector = NestedObjects(using='default')
                        collector.collect([person,])
                        objects = collector.nested()
                        related = [ o for o in objects[-1] if not isinstance(o, (Alias, Person, SearchRule, PersonalApiKey)) ]
                        if len(related) > 0:
                            self.stderr.write("Person record #%-6s %s has unexpected related records" % (person.pk, person.ascii_name()))

                    # Historical records using simple_history has on_delete=DO_NOTHING, so
                    # we have to do explicit deletions:
                    id = person.id
                    person.delete()
                    Person.history.filter(id=id).delete()
                    Email.history.filter(person_id=id).delete()

        # Deal with remaining persons (lacking consent, but with legitimate interest)
        persons = Person.objects.exclude(consent=True)
        persons = persons.exclude(id=1)
        self.stdout.write("Found %d remaining persons with information for which we don't have consent." % (persons.count(), ))
        if persons.count() > 0:
            self.stdout.write("Removing personal information requiring consent ...")
            for person in (persons if dry_run else tqdm(persons)):
                fields = ', '.join(person.needs_consent())
                if dry_run:
                    self.stdout.write(("Would remove info for #%-6d: (%s) %-32s %-48s %s" % (person.pk, person.time, person.ascii_name(), "<%s>"%person.email(), fields)).encode('utf8'))
                else:
                    if person.name_from_draft:
                        log("Using name info from draft for #%-6d %s: no consent, no roles" % (person.pk, person))
                        person.name = person.name_from_draft
                        person.ascii = unidecode_name(person.name_from_draft)
                    if person.biography:
                        log("Deleting biography for #%-6d %s: no consent, no roles" % (person.pk, person))
                        person.biography = ''
                        person.save()
                    if person.user_id:
                        if User.objects.filter(id=person.user_id).exists():
                            log("Deleting communitylist for #%-6d %s: no consent, no roles" % (person.pk, person))
                            person.user.communitylist_set.all().delete()
                    for email in person.email_set.all():
                        if not email.origin.split(':')[0] in ['author', 'role', 'reviewer', 'liaison', 'shepherd', ]:
                            log("Deleting email <%s> for #%-6d %s: no consent, no roles" % (email.address, person.pk, person))
                            address = email.address
                            email.delete()
                            Email.history.filter(address=address).delete()

        emails = Email.objects.filter(origin='', person__consent=False)
        self.stdout.write("Found %d emails without origin for which we lack consent." % (emails.count(), ))
        if dry_run:
            self.stdout.write("Would delete %d email records without origin and consent" % (emails.count(), ))
        else:
            if emails.count():
                log("Deleting %d email records without origin and consent" % (emails.count(), ))
                addresses = emails.values_list('address', flat=True)
                emails.delete()
                Email.history.filter(address__in=addresses).delete()
                
