# Copyright The IETF Trust 2007, All Rights Reserved

from ietf.group.models import Group
from django.shortcuts import render_to_response
from django.template import RequestContext

def groups(request):
    groups = Group.objects.filter(type__in=("wg", "rg"), list_archive__startswith='http').order_by("acronym")

    return render_to_response("mailinglists/group_archives.html", { "groups": groups },
                              context_instance=RequestContext(request))

