import datetime
import syslog
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ietf.utils.mail import send_mail

from ietf.dbtemplate.models import DBTemplate

from ietf.nomcom.models import Nominee, NomCom
from ietf.nomcom.utils import NOMINEE_REMINDER_TEMPLATE


class Command(BaseCommand):
    help = (u"Send reminders to nominees")
    option_list = BaseCommand.option_list + (
         make_option('--nomcom-year', dest='year', help='NomCom year'),
        )

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
        nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
        mail_path = nomcom_template_path + NOMINEE_REMINDER_TEMPLATE
        mail_template = DBTemplate.objects.filter(group=nomcom.group, path=mail_path)
        mail_template = mail_template and mail_template[0] or None
        subject = 'IETF Nomination Information'
        from_email = settings.NOMCOM_FROM_EMAIL

        if nomcom.reminder_interval:
            nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().filter(nomineeposition__state='pending').distinct()
            for nominee in nominees:
                positions = []
                for np in nominee.nomineeposition_set.all():
                    nomination_date = np.time.date()
                    if not (today - nomination_date).days <= 0:
                        if (today - nomination_date).days % nomcom.reminder_interval == 0:
                            positions.append(np.position)
                if positions:
                    to_email = nominee.email.address
                    context = {'positions': ', '.join([p.name for p in positions])}
                    send_mail(None, to_email, from_email, subject, mail_path, context)
                    syslog.syslog(u"Sent reminder to %s" % to_email)
        else:
            if nomcom.reminderdates_set.filter(date=today):
                nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().filter(nomineeposition__state='pending').distinct()
                for nominee in nominees:
                    to_email = nominee.email.address
                    positions = ', '.join([nominee_position.position.name for nominee_position in nominee.nomineeposition_set.pending()])
                    context = {'positions': positions}
                    send_mail(None, to_email, from_email, subject, mail_path, context)
                    syslog.syslog(u"Sent reminder to %s" % to_email)
