from optparse import make_option

from django.core.management.base import BaseCommand

from ietf.group.models import Group
from ietf.liaisons.mails import send_sdo_reminder


class Command(BaseCommand):
    help = (u"Send a remind to each SDO Liaison Manager to update the list of persons authorized to send liaison statements on behalf of his SDO")
    option_list = BaseCommand.option_list + (
        make_option('-s', '--sdo-pk', dest='sdo_pk',
                    help='Send the reminder to the SDO with this primary key. If not provided reminder will be sent to all SDOs'),
        )

    def handle(self, *args, **options):
        sdo_pk = options.get('sdo_pk', None)
        return_output = options.get('return_output', False)

        msg_list = send_reminders_to_sdos(sdo_pk=sdo_pk)
        return msg_list if return_output else None

def send_reminders_to_sdos(sdo_pk=None):
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
        msgs.append(msg)

    return msgs