from optparse import make_option
from email.utils import parseaddr
import syslog

from django.core.management.base import BaseCommand, CommandError

from ietf.nomcom.utils import parse_email
from ietf.nomcom.models import NomCom, Feedback


class Command(BaseCommand):
    help = (u"Registry feedback from email. Usage: feeback_email --nomcom-year <nomcom-year> --email-file <email-file>")
    option_list = BaseCommand.option_list + (
         make_option('--nomcom-year', dest='year', help='NomCom year'),
         make_option('--email-file', dest='email', help='Feedback email'),
        )

    def handle(self, *args, **options):
        email = options.get('email', None)
        year = options.get('year', None)
        msg = None
        nomcom = None
        help_message = 'Usage: feeback_email --nomcom-year <nomcom-year> --email-file <email-file>'

        if not year:
            raise CommandError(help_message)

        if not email:
            raise CommandError(help_message)
        else:
            msg = open(email, "r").read()

        try:
            nomcom = NomCom.objects.get(group__acronym__icontains=year,
                                        group__state__slug='active')
        except NomCom.DoesNotExist:
            raise CommandError("NomCom %s does not exist or it isn't active" % year)

        by, subject, body = parse_email(msg)
        body = 'Subject: %s\n\n%s' % (subject, body)
        name, addr = parseaddr(by)

        feedback = Feedback(nomcom=nomcom,
                            author=addr,
                            comments=body)
        feedback.save()

        syslog.syslog(u"Read feedback email by %s" % by)
