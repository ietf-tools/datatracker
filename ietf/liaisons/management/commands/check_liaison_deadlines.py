import datetime

from django.core.management.base import BaseCommand

from ietf.liaisons.models import LiaisonStatement
from ietf.liaisons.mails import possibly_send_deadline_reminder


class Command(BaseCommand):
    help = (u"Check liaison deadlines and send a reminder if we are close to a deadline")

    def handle(self, *args, **options):
        today = datetime.date.today()
        
        cutoff = today - datetime.timedelta(14)

        for l in LiaisonStatement.objects.filter(action_taken=False, deadline__gte=cutoff).exclude(deadline=None):
            r = possibly_send_deadline_reminder(l)
            if r:
                print 'Liaison %05s#: Deadline reminder sent!' % l.pk
