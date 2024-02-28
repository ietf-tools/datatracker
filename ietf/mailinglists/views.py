# Copyright The IETF Trust 2007-2022, All Rights Reserved

from django.shortcuts import render

import debug  # pyflakes:ignore

from ietf.group.models import Group
from ietf.mailinglists.models import NonWgMailingList


def groups(request):
    groups = (
        Group.objects.filter(
            type__features__acts_like_wg=True, list_archive__startswith="http"
        )
        .exclude(state__in=("bof", "conclude"))
        .order_by("acronym")
    )

    return render(request, "mailinglists/group_archives.html", {"groups": groups})


def nonwg(request):
    lists = NonWgMailingList.objects.order_by("name")
    return render(request, "mailinglists/nonwg.html", {"lists": lists})
