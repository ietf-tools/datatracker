# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.shortcuts import render

import debug                            # pyflakes:ignore

from ietf.meeting.helpers import get_current_ietf_meeting_num
from ietf.name.models import CountryName

def stats_index(request):
    """Render the statistics index page with the current meeting number as it is required by the meeting menu item."""
    current_meeting = get_current_ietf_meeting_num()
    return render(request, "stats/index.html", {
        "current_meeting": current_meeting
    })

def known_countries_list(request, stats_type=None, acronym=None):
    """Render a list of known countries with their aliases."""
    countries = CountryName.objects.prefetch_related("countryalias_set")
    for c in countries:
        # the sorting is a bit of a hack - it puts the ISO code first
        # since it was added in a migration
        c.aliases = sorted(c.countryalias_set.all(), key=lambda a: a.pk)

    return render(request, "stats/known_countries_list.html", {
        "countries": countries,
    })
