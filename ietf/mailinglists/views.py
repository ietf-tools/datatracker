# Copyright The IETF Trust 2007, All Rights Reserved

import re

from django.shortcuts import render

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.mailinglists.models import List

def groups(request):
    groups = Group.objects.filter(type__features__acts_like_wg=True, list_archive__startswith='http').exclude(state__in=('bof', 'conclude')).order_by("acronym")

    return render(request, "mailinglists/group_archives.html", { "groups": groups } )

def nonwg(request):
    groups = Group.objects.filter(type__features__acts_like_wg=True).exclude(state__in=['bof', 'conclude']).order_by("acronym")

    #urls = [ g.list_archive for g in groups if '.ietf.org' in g.list_archive ]

    wg_lists = set()
    for g in groups:
        wg_lists.add(g.acronym)
        match = re.search(r'^(https?://mailarchive.ietf.org/arch/(browse/|search/\?email-list=))(?P<name>[^/]*)/?$', g.list_archive)
        if match:
            wg_lists.add(match.group('name').lower())

    lists = List.objects.filter(advertised=True)
    #debug.show('lists.count()')
    lists = lists.exclude(name__in=wg_lists).order_by('name')
    #debug.show('lists.count()')
    return render(request, "mailinglists/nonwg.html", { "lists": lists } )
