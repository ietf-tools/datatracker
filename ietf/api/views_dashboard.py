# Copyright The IETF Trust 2023, All Rights Reserved

import datetime

from collections import defaultdict
from dateutil import rrule
from django.db.models import Subquery, OuterRef
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ietf.api.ietf_utils import requires_api_token

from ietf.group.models import Group, ChangeStateGroupEvent
from ietf.doc.models import NewRevisionDocEvent

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def groups_opened_closed(request, groupType, startYear, endYear):

    # TODO validate input
    startYear = int(startYear)
    endYear = int(endYear)

    qs = Group.objects.filter(type_id=groupType).annotate(
        opened=Subquery(
            ChangeStateGroupEvent.objects.filter(state="active",group_id=OuterRef("pk")).values_list("time",flat=True).order_by("-time")[:1]
        )
    ).annotate(
        closed=Subquery(
            ChangeStateGroupEvent.objects.filter(state="conclude",group_id=OuterRef("pk")).values_list("time",flat=True).order_by("-time")[:1]
        )
    )
    response = []
    for year in range(startYear,endYear+1):
        response.append(
            {
                "year": year,
                "opened": [
                    { 
                        "acronym": group.acronym,
                        "parent_acronym": group.parent.acronym if group.parent else "",
                        "date": group.opened
                    }
                    for group in qs.filter(opened__year=year)
                ],
                "closed": [
                    { 
                        "acronym": group.acronym,
                        "parent_acronym": group.parent.acronym if group.parent else "",
                        "date": group.closed
                    }
                    for group in qs.filter(closed__year=year)
                ]
            }
        )
    return JsonResponse(response, safe=False)

@csrf_exempt
@requires_api_token("ietf.api.views_dashboard")
def submissions(request, start, end):

    # TODO: validate inputs
    dtstart = datetime.datetime.strptime(start, "%Y-%m").astimezone(datetime.timezone.utc)
    dtend = datetime.datetime.strptime(end, "%Y-%m").astimezone(datetime.timezone.utc)

    qs = NewRevisionDocEvent.objects.filter(doc__type_id="draft")
    # qs = Document.objects.filter(type_id="draft").annotate(
    #     rev_date = NewRevisionDocEvent.objects.filter(doc_id=OuterRef('pk')).order_by("-time").values_list("time",flat=True)[:1]
    # ).distinct().annotate(
    #     rev_00_date = NewRevisionDocEvent.objects.filter(doc_id=OuterRef('pk'),rev="00").order_by("-time").values_list("time",flat=True)[:1]
    # )

    response = []
    for interval_start in rrule.rrule(rrule.MONTHLY, dtstart=dtstart, until=dtend):
        interval_end = (interval_start+datetime.timedelta(days=32)).replace(day=1)
        response.append(
            {
                "date": interval_start,
                "all": qs.filter(time__gte=interval_start,time__lt=interval_end).values_list("doc_id",flat=True).distinct().count(),
                "all-00": qs.filter(time__gte=interval_start,time__lt=interval_end, rev="00").values_list("doc_id",flat=True).distinct().count(),
                "wg-00": qs.filter(time__gte=interval_start,time__lt=interval_end, rev="00", doc__group__type_id="wg").values_list("doc_id",flat=True).distinct().count()
            }
        )

    return JsonResponse(response, safe=False)

