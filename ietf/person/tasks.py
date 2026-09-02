# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from ietf.utils import log
from ietf.utils.mail import send_mail
from .models import Person, PersonalApiKey, PersonApiKeyEvent
from .utils import ensure_primary_uuid


@shared_task
def send_apikey_usage_emails_task(days):
    """Send usage emails to Persons who have API keys"""
    earliest = timezone.now() - datetime.timedelta(days=days)
    keys = PersonalApiKey.objects.filter(
        valid=True,
        personapikeyevent__time__gt=earliest,
    ).distinct()
    for key in keys:
        events = PersonApiKeyEvent.objects.filter(key=key, time__gt=earliest)
        count = events.count()
        events = events[:32]
        if count:
            key_name = key.hash()[:8]
            subject = "API key usage for key '%s' for the last %s days" % (
                key_name,
                days,
            )
            to = key.person.email_address()
            frm = settings.DEFAULT_FROM_EMAIL
            send_mail(
                None,
                to,
                frm,
                subject,
                "utils/apikey_usage_report.txt",
                {
                    "person": key.person,
                    "days": days,
                    "key": key,
                    "key_name": key_name,
                    "count": count,
                    "events": events,
                },
            )

@shared_task
def purge_personal_api_key_events_task(keep_days):
    keep_since = timezone.now() - datetime.timedelta(days=keep_days)
    old_events = PersonApiKeyEvent.objects.filter(time__lt=keep_since)
    count = len(old_events)
    old_events.delete()
    log.log(f"Deleted {count} PersonApiKeyEvents older than {keep_since}")


@shared_task
def check_person_uuids_task(fix=False):
    """Report - and optionally repair - Persons whose UUID set is inconsistent

    Every Person is supposed to have exactly one primary UUID. Assignment is an explicit
    assign_primary_uuid() call at each site that creates a Person, so a site added
    without one leaves Persons that cannot be named to any external system. This finds
    them.

    Checks for exactly one rather than at least one. A partial unique constraint should
    make more than one impossible, so finding one means something is grossly wrong with
    the data and worth saying out loud - and this is the job that claims the condition
    holds, so it may as well test it.
    """
    broken = (
        Person.objects.annotate(
            uuid_count=Count("uuids", distinct=True),
            primary_count=Count("uuids", filter=Q(uuids__primary=True), distinct=True),
        )
        .exclude(primary_count=1)
        .order_by("pk")
    )

    count = 0
    for person in broken:
        count += 1
        if person.primary_count > 1:
            # ensure_primary_uuid() cannot resolve this - it would pick one of the
            # primaries arbitrarily. Needs a human to decide which one survives.
            log.log(
                f"Person {person.pk} ({person.name}): {person.primary_count} primary "
                f"UUIDs, which the unique constraint should have prevented - not "
                f"repairing automatically"
            )
            continue
        problem = "no UUIDs at all" if person.uuid_count == 0 else "no primary UUID"
        log.log(f"Person {person.pk} ({person.name}): {problem}")
        if fix:
            row = ensure_primary_uuid(person)
            log.log(f"Person {person.pk}: primary UUID is now {row.uuid}")

    if count == 0:
        log.log("check_person_uuids: every Person has exactly one primary UUID")
    else:
        log.log(
            f"check_person_uuids: {count} Person(s) "
            f"{'repaired' if fix else 'need attention'}"
        )
    return count


@shared_task
def push_person_uuids_task(person_pk):
    """Push a Person's UUID set to Authentik

    Enqueued by ietf.person.utils.queue_person_uuid_push whenever the set changes. The
    Authentik client does not exist yet, so for now this records the desired state that
    will be pushed.
    """
    person = Person.objects.filter(pk=person_pk).first()
    if person is None:
        log.log(f"Not pushing UUIDs for Person {person_pk}: no such Person")
        return
    log.log(
        f"Person {person_pk} UUIDs: primary={person.primary_uuid} "
        f"prior={[str(u) for u in person.prior_uuids]}"
    )
