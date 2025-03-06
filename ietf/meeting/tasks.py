# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task

from .views import generate_agenda_data
from .utils import migrate_registrations


@shared_task
def agenda_data_refresh():
    generate_agenda_data(force_refresh=True)


@shared_task
def migrate_registrations_task(initial=False):
    """ Migrate ietf.stats.MeetingRegistration to ietf.meeting.Registration
        If initial is True, migrate all meetings otherwise only future meetings.
        This function is idempotent. It can be run regularly from cron.
    """
    migrate_registrations(initial=initial)
