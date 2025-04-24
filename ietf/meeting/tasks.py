# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task
from django.utils import timezone

from ietf.utils import log
from .models import Meeting
from .utils import generate_proceedings_content
from .views import generate_agenda_data
from .utils import migrate_registrations, check_migrate_registrations


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


@shared_task
def check_migrate_registrations_task():
    """ Compare MeetingRegistration with Registration to ensure
        all records migrated
    """
    check_migrate_registrations()


def proceedings_content_refresh_task(*, all=False):
    """Refresh meeting proceedings cache

    If `all` is `False`, then refreshes the cache for meetings whose numbers modulo
    24 equal the current hour number (0-23). Scheduling the task once per hour will
    then result in all proceedings being recomputed daily, with no more than two per
    hour (now) or a few per hour in the next decade. That keeps the computation time
    to under a couple minutes on our current production system.

    If `all` is True, refreshes all meetings
    """
    now = timezone.now()

    for meeting in Meeting.objects.filter(type_id="ietf").order_by("number"):
        if meeting.proceedings_format_version == 1:
            continue  # skip v1 proceedings, they're stored externally
        num = meeting.get_number()  # convert str -> int
        if num is None:
            log.log(
                f"Not refreshing proceedings for meeting {meeting.number}: "
                f"type is 'ietf' but get_number() returned None"
            )
        elif all or (num % 24 == now.hour):
            log.log(f"Refreshing proceedings for meeting {meeting.number}...")
            generate_proceedings_content(meeting, force_refresh=True)
