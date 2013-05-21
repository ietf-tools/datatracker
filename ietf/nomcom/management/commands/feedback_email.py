from optparse import make_option
import syslog

from django.core.management.base import BaseCommand, CommandError

from ietf.nomcom.models import NomCom
from ietf.nomcom.utils import create_feedback_email


class Command(BaseCommand):
    help = (u"Registry feedback from email. Usage: feeback_email --nomcom-year <nomcom-year> --email-file <email-file>")
    option_list = BaseCommand.option_list + (
         make_option('--nomcom-year', dest='year', help='NomCom year'),
         make_option('--email-file', dest='email', help='Feedback email'),)

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

        feedback = create_feedback_email(nomcom, msg)
        syslog.syslog(u"Read feedback email by %s" % feedback.author)
