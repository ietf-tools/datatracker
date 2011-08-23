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
        sdo_pk = options.get('sdo_pk', None)
        return_output = options.get('return_output', False)

        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            msg_list = send_reminders_to_sdos(sdo_pk=sdo_pk)
            return msg_list if return_output else None

        query = SDOs.objects.all().order_by('pk')
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


def send_reminders_to_sdos(sdo_pk=None):
    from redesign.group.models import Group
    from ietf.liaisons.mails import send_sdo_reminder
    
    sdos = Group.objects.filter(type="sdo").order_by('pk')
    if sdo_pk:
        sdos = sdos.filter(pk=sdo_pk)

    if not sdos:
        print "No SDOs found!"
        
    msgs = []
    for sdo in sdos:
        body = send_sdo_reminder(sdo)

        if not body:
            msg = u'%05s#: %s has no liaison manager' % (sdo.pk, sdo.name)
        else:
            msg = u'%05s#: %s mail sent!' % (sdo.pk, sdo.name)

        print msg
        msgs.append(msg)

    return msgs
        

