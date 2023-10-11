# Copyright The IETF Trust 2023, All Rights Reserved

from collections import defaultdict
from django.db.models import Subquery, OuterRef
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ietf.api.ietf_utils import requires_api_token

from ietf.group.models import Group, ChangeStateGroupEvent

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
