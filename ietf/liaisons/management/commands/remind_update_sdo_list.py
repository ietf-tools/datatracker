from optparse import make_option

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from ietf.liaisons.models import SDOs


class Command(BaseCommand):
    help = (u"Send a remind to each SDO Liaison Manager to update the list of persons authorized to send liaison statements on behalf of his SDO")
    option_list = BaseCommand.option_list + (
        make_option('-s', '--sdo-pk', dest='sdo_pk',
                    help='Send the reminder to the SDO whith this primary key. If not provided reminder will be sent to all SDOs'),
        )


    def send_mail_to(self, person, sdo):
        subject = 'Request for update list of authorized individuals'
        email = person.email()[1]
        name = ' '.join([i for i in (person.name_prefix, person.first_name, person.middle_initial, person.last_name, person.name_suffix) if i])
        authorized_list = [i.person for i in sdo.sdoauthorizedindividual_set.all()]
        body = render_to_string('liaisons/sdo_reminder.txt',
                                {'manager_name': name,
                                 'sdo_name': sdo.sdo_name,
                                 'individuals': authorized_list,
                                })
        mail = EmailMessage(subject=subject,
                            to=[email],
                            from_email=settings.LIAISON_UNIVERSAL_FROM,
                            body = body)
        if not settings.DEBUG:
            mail.send()
            msg = '%05s#: %s Mail Sent!' % (sdo.pk, sdo.sdo_name)
        else:
            msg = '%05s#: %s Mail Not Sent because in DEBUG mode!' % (sdo.pk, sdo.sdo_name)
        return msg

    def handle(self, *args, **options):
        query = SDOs.objects.all().order_by('pk')
        sdo_pk = options.get('sdo_pk', None)
        return_output = options.get('return_output', False)
        if sdo_pk:
            query = query.filter(pk=sdo_pk)

        msg_list = []
        for sdo in query:
            manager = sdo.liaisonmanager()
            if manager:
                msg = self.send_mail_to(manager.person, sdo)
            else:
                msg = '%05s#: %s has no liaison manager' % (sdo.pk, sdo.sdo_name)
            print msg
            msg_list.append(msg)
        if return_output:
            return msg_list
