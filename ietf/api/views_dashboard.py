# Copyright The IETF Trust 2023, All Rights Reserved

import debug # pyflakes: ignore

import datetime

from collections import Counter

from dateutil import rrule
from django.db.models import Subquery, OuterRef, Min
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ietf.api.ietf_utils import requires_api_token

from ietf.group.models import Group, ChangeStateGroupEvent
from ietf.doc.models import NewRevisionDocEvent
from ietf.meeting.models import Session
from ietf.stats.models import MeetingRegistration

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def groups_opened_closed(request):

    qs = Group.objects.filter(type_id__in=["wg","rg","program"]).annotate(
        opened=Subquery(
            ChangeStateGroupEvent.objects.filter(state="active",group_id=OuterRef("pk")).values_list("time",flat=True).order_by("-time")[:1]
        )
    ).annotate(
        closed=Subquery(
            ChangeStateGroupEvent.objects.filter(state="conclude",group_id=OuterRef("pk")).values_list("time",flat=True).order_by("-time")[:1]
        )
    )
    response = []

    for group in qs.exclude(opened__isnull=True):
        response.append(
            { 
                "group_type": group.type_id,
                "acronym": group.acronym,
                "parent_acronym": group.parent.acronym if group.parent else "",
                "date": group.opened,
                "state": "opened"
            }
        )
    for group in qs.exclude(closed__isnull=True):
        response.append(
            { 
                "group_type": group.type_id,
                "acronym": group.acronym,
                "parent_acronym": group.parent.acronym if group.parent else "",
                "date": group.closed,
                "state": "closed"
            }
        )
    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def submissions(request):

    # dtstart = datetime.datetime.strptime(start, "%Y-%m").astimezone(datetime.timezone.utc)
    # dtend = datetime.datetime.strptime(end, "%Y-%m").astimezone(datetime.timezone.utc)
    dtstart = NewRevisionDocEvent.objects.filter(doc__type_id="draft").aggregate(Min("time"))["time__min"].replace(day=1,hour=0,minute=0,second=0)
    dtend = timezone.now().replace(day=1,hour=0,minute=0,second=0)

    qs = NewRevisionDocEvent.objects.filter(doc__type_id="draft")

    response = []
    for interval_start in rrule.rrule(rrule.MONTHLY, dtstart=dtstart, until=dtend):
        interval_end = (interval_start+datetime.timedelta(days=32)).replace(day=1)
        response.append(
            {
                "date": interval_start,
                "all-subs": qs.filter(time__gte=interval_start,time__lt=interval_end).count(),
                "distinct-ids": qs.filter(time__gte=interval_start,time__lt=interval_end).values_list("doc_id",flat=True).distinct().count(),
                "all-00": qs.filter(time__gte=interval_start,time__lt=interval_end, rev="00").values_list("doc_id",flat=True).distinct().count(),
                "wg-00": qs.filter(time__gte=interval_start,time__lt=interval_end, rev="00", doc__group__type_id="wg").values_list("doc_id",flat=True).distinct().count()
            }
        )

    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def interims(request):

    response = [
        {
            "group_type": s.group.type_id,
            "acronym": s.group.acronym,
            "parent_acronym": s.group.parent and s.group.parent.acronym,
            "time": s.official_timeslotassignment().timeslot.time # TODO: Optimize this
        }
        for s in Session.objects.filter(meeting__type_id="interim", schedulingevent__status_id="sched")
    ]

    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def registration(request):

    onsite_counts = Counter(MeetingRegistration.objects.filter(reg_type="onsite").values_list("meeting__number","country_code"))
    onsite_counts += Counter(MeetingRegistration.objects.filter(reg_type="").exclude(meeting__number=107).values_list("meeting__number","country_code"))
    remote_counts = Counter(MeetingRegistration.objects.filter(reg_type="remote").values_list("meeting__number","country_code"))
    remote_counts += Counter(MeetingRegistration.objects.filter(reg_type="",meeting__number=107).values_list("meeting__number","country_code"))
    # This is off by trivial for these meetings that have reg_type="" where they shouldn't
    # '110': 3, '108': 1, '112': 1})
    # Not fixing it here - that's data cleanup that needs to happen.
    keys = set(onsite_counts.keys())
    keys.update(set(remote_counts.keys()))
    response = [
        {
            "meeting": key[0],
            "country": key[1],
            "onsite": onsite_counts[key],
            "remote": remote_counts[key],
        }
        for key in keys
    ]

    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def adopted(request):

    qs = NewRevisionDocEvent.objects.filter(
        doc__type_id="draft",doc__group__type_id="wg", rev="00"
    ).select_related("doc").annotate(
        area=Subquery(
            Group.objects.filter(pk=OuterRef("doc__group_id")).values_list('parent__acronym',flat=True)[:1]
        )
    )

    dtstart = qs.aggregate(Min("time"))["time__min"].replace(day=1,hour=0,minute=0,second=0)
    dtend = timezone.now().replace(day=1,hour=0,minute=0,second=0)

    response = []
    for interval_start in rrule.rrule(rrule.MONTHLY, dtstart=dtstart, until=dtend):
        interval_end = (interval_start+datetime.timedelta(days=32)).replace(day=1)
        for area in set(qs.filter(time__gte=interval_start,time__lt=interval_end).values_list("area", flat=True)):
            response.append(
                {
                    "date": interval_start,
                    "area": area,
                    "count": qs.filter(time__gte=interval_start,time__lt=interval_end, area=area).values_list("doc_id",flat=True).distinct().count()
                }
            )

    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def areas(request):

    response=[
        {
            "acronym": group.acronym,
            "status": group.state_id
        }
        for group in Group.objects.filter(type_id="area")
    ]


    return JsonResponse(response, safe=False)
