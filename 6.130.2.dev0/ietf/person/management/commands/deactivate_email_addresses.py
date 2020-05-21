# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import flufl.bounce
import io
import mailbox
import sys

from tqdm import tqdm

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email

import debug                            # pyflakes:ignore

from ietf.person.models import Email, PersonEvent


class Command(BaseCommand):
    help = ("""
        Deactivate bouncing email addresses.

        Take one or more email addresses to deactivate from the command line,
        or read delivery-status emails from an mbox file and extract addresses        with delivery failures from that, and mark them inactive.

        """)

    def add_arguments(self, parser):
        parser.add_argument('-n', '--dry-run', action='store_true', default=False,
            help="Don't deactivate email addresses, just list what would be done.")
        parser.add_argument('-f', '--file', help="Process an mbox file containing bounce messages")
        parser.add_argument('-r', '--reason', default="bounce", help='The reason for deactivation. Default: "%(default)s".')
        parser.add_argument('address', nargs='*')

    def is_valid_email(self, s):
        try:
            validate_email(s)
        except ValidationError:
            return False
        return True


    def handle(self, *args, **options):
        addresses = options['address']
        if options['file']:
            self.stderr.write('Extracting bounced addresses from mbox file "%s":\n' % (options['file']))
            mbox = mailbox.mbox(options['file'], create=False)
            messages = {}
            for msg in tqdm(mbox):
                recipients = flufl.bounce.scan_message(msg)
                # Special fix for reports from cisco, which don't convey the
                # original recipent address:
                recipients = [ r.replace('@exch.cisco.com', '@cisco.com') for r in recipients ]
                for r in recipients:
                    messages[r] = msg
                addresses += recipients
        addresses = [ a.strip() for a in addresses ]
        addresses = [ a for a in addresses if self.is_valid_email(a) ]
        if options['dry_run']:
            for a in addresses:
                email = Email.objects.filter(address=a).first()
                if email:
                    if email.person_id:
                        self.stdout.write('Would deactivate <%s> (person %s)\n' % (a, email.person.plain_ascii()))
                    else:
                        self.stderr.write('No person is associated with <%s>\n' % (a, ))
                else:
                    self.stderr.write('Address not found: <%s>\n' % (a, ))
                    with io.open('./failed', 'a') as failed:
                        failed.write(messages[a].as_string(unixfrom=True))
                        failed.write('\n')

        else:
            self.stderr.write('Setting email addresses to inactive:\n')
            not_found = []
            for a in tqdm(addresses):
                email = Email.objects.filter(address=a).first()
                if email and email.person_id:
                    if not email.active:
                        continue
                    email.active = False
                    email.origin = email.person.user.username if email.person.user_id else ('script: %s deactivation' % options['reason'])
                    email.save()
                    PersonEvent.objects.create(person=email.person, type='email_address_deactivated',
                        desc="Deactivated the email addres <%s>. Reason: %s" % (email.address, options['reason']) )
                else:
                    if email is None:
                        not_found.append(a)
                    elif not email.person_id:
                        self.stderr.write("Could not deactivate <%s>: Null person record\n" % (a, ))
                    else:
                        self.stderr.write("Unexpected error when processing <%s>: Quitting." % (a, ))
                        sys.exit(1)
            for a in not_found:
                self.stderr.write('Address not found: <%s>\n' % (a, ))
                        
