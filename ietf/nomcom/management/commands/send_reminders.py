import datetime
import syslog
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from ietf.nomcom.models import Nominee, NomCom
from nomcom.utils import send_reminder_to_nominee


class Command(BaseCommand):
    help = (u"Send reminders to nominees")
    option_list = BaseCommand.option_list + (
         make_option('--nomcom-year', dest='year', help='NomCom year'),)

    def handle(self, *args, **options):
        year = options.get('year', None)
        help_message = 'Usage: send_reminders --nomcom-year <nomcom-year>'

        if not year:
            raise CommandError(help_message)

        try:
            nomcom = NomCom.objects.get(group__acronym__icontains=year,
                                        group__state__slug='active')
        except NomCom.DoesNotExist:
            raise CommandError("NomCom %s does not exist or it isn't active" % year)

        today = datetime.date.today()

        if nomcom.reminder_interval:
            nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().filter(nomineeposition__state='pending').distinct()
            for nominee in nominees:
                for nominee_position in nominee.nomineeposition_set.all():
                    nomination_date = nominee_position.time.date()
                    if not (today - nomination_date).days <= 0:
                        if (today - nomination_date).days % nomcom.reminder_interval == 0:
                            send_reminder_to_nominee(nominee_position)
                            syslog.syslog(u"Sent reminder to %s" % nominee_position.nominee.email.address)
                            print u"Sent reminder to %s" % nominee_position.nominee.email.address
        else:
            if nomcom.reminderdates_set.filter(date=today):
                nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().filter(nomineeposition__state='pending').distinct()
                for nominee in nominees:
                    for nominee_position in nominee.nomineeposition_set.pending():
                        send_reminder_to_nominee(nominee_position)
                        syslog.syslog(u"Sent reminder to %s" % nominee_position.nominee.email.address)
                        print u"Sent reminder (by dates) to %s" % nominee_position.nominee.email.address
