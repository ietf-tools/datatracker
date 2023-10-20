# Copyright The IETF Trust 2023, All Rights Reserved

import datetime

from dateutil import rrule
from django.db.models import Subquery, OuterRef, Min
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ietf.api.ietf_utils import requires_api_token

from ietf.group.models import Group, ChangeStateGroupEvent
from ietf.doc.models import NewRevisionDocEvent
from ietf.meeting.models import Session

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
    dtstart = NewRevisionDocEvent.objects.aggregate(Min("time"))["time__min"].replace(day=1,hour=0,minute=0,second=0)
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
