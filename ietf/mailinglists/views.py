# Copyright The IETF Trust 2007, All Rights Reserved

from ietf.group.models import Group
from django.shortcuts import render

def groups(request):
    groups = Group.objects.filter(type__in=("wg", "rg"), list_archive__startswith='http').order_by("acronym")

    return render(request, "mailinglists/group_archives.html", { "groups": groups } )

