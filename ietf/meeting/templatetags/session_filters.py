# Copyright The IETF Trust 2023, All Rights Reserved
from django import template

from ietf.name.models import SessionStatusName

register = template.Library()


@register.filter
def presented_versions(session, doc):
    sp = session.sessionpresentation_set.filter(document=doc)
    if not sp:
        return "Document not in session"
    else:
        rev = sp.first().rev
        return rev if rev else "(current)"


@register.filter
def can_manage_materials(session, user):
    return session.can_manage_materials(user)


@register.filter
def describe_with_tz(session):
    # Very similar to session.__str__, but doesn't treat interims differently from sessions at an IETF meeting
    # and displays the timeslot in the meeting's timezone.

    if session is None:
        return ""

    status_id = None
    if hasattr(session, "current_status"):
        status_id = session.current_status
    elif session.pk is not None:
        latest_event = session.schedulingevent_set.order_by("-time", "-id").first()
        if latest_event:
            status_id = latest_event.status_id

    if status_id in ("canceled", "disappr", "notmeet", "deleted"):
        ss0name = "(%s)" % SessionStatusName.objects.get(slug=status_id).name
    else:
        ss0name = "(unscheduled)"
        ss = session.timeslotassignments.filter(
            schedule__in=[
                session.meeting.schedule,
                session.meeting.schedule.base if session.meeting.schedule else None,
            ]
        ).order_by("timeslot__time")
        if ss:
            ss0name = ",".join(
                x.timeslot.time.astimezone(session.meeting.tz()).strftime("%a-%H%M")
                for x in ss
            )
            ss0name += f" {session.meeting.tz()}"
    return f"{session.meeting}: {session.group.acronym} {session.name} {ss0name}"
