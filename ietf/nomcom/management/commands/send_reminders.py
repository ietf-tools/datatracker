# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import syslog

from django.core.management.base import BaseCommand

from ietf.nomcom.models import NomCom, NomineePosition
from ietf.nomcom.utils import send_accept_reminder_to_nominee,send_questionnaire_reminder_to_nominee

def log(message):
    syslog.syslog(message)

def is_time_to_send(nomcom,send_date,nomination_date):
    if nomcom.reminder_interval:
        days_passed = (send_date - nomination_date).days
        return days_passed > 0 and days_passed % nomcom.reminder_interval == 0
    else:
        return bool(nomcom.reminderdates_set.filter(date=send_date))

class Command(BaseCommand):
    help = ("Send acceptance and questionnaire reminders to nominees")

    def handle(self, *args, **options):
        for nomcom in NomCom.objects.filter(group__state__slug='active'):
            nps = NomineePosition.objects.filter(nominee__nomcom=nomcom,nominee__duplicated__isnull=True)
            for nominee_position in nps.pending():
                if is_time_to_send(nomcom, datetime.date.today(), nominee_position.time.date()):
                    send_accept_reminder_to_nominee(nominee_position)
                    log('Sent accept reminder to %s' % nominee_position.nominee.email.address)
            for nominee_position in nps.accepted().without_questionnaire_response():
                if is_time_to_send(nomcom, datetime.date.today(), nominee_position.time.date()):
                    send_questionnaire_reminder_to_nominee(nominee_position)
                    log('Sent questionnaire reminder to %s' % nominee_position.nominee.email.address)
