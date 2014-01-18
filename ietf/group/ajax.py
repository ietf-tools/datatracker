import datetime
import logging
import json

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404

from ietf.group.models import Group

def group_json(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)

    return HttpResponse(json.dumps(group.json_dict(request.build_absolute_uri('/')),
                                   sort_keys=True, indent=2),
                        content_type="text/json")

