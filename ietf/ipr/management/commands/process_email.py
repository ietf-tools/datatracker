import sys
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from ietf.utils.log import log
from ietf.ipr.mail import process_response_email

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    help = (u"Process incoming email responses to ipr mail")
    option_list = BaseCommand.option_list + (
         make_option('--email-file', dest='email', help='File containing email (default: stdin)'),)

    def handle(self, *args, **options):
        email = options.get('email', None)
        msg = None

        if not email:
            msg = sys.stdin.read()
        else:
            msg = open(email, "r").read()

        try:
            message = process_response_email(msg)
            log(u"Received IPR email from %s" % message.frm)
        except ValueError as e:
            raise CommandError(e)
