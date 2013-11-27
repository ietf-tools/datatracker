# Copyright The IETF Trust 2007, All Rights Reserved

import re

from django.views.generic.simple import direct_to_template
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q

from ietf.idtracker.models import ChairsHistory
from ietf.idtracker.models import Role
from ietf.group.models import Group, GroupEvent
from ietf.message.models import Message

def nomcom(request):
    address_re = re.compile("<.*>")
    
    nomcoms = list(Group.objects.filter(acronym__startswith="nomcom").exclude(name="nomcom"))

    regimes = []
    
    for n in nomcoms:
        e = GroupEvent.objects.filter(group=n, type="changed_state", changestategroupevent__state="active").order_by('time')[:1]
        n.start_year = e[0].time.year if e else 0
        if n.start_year <= 2003:
            continue
        e = GroupEvent.objects.filter(group=n, type="changed_state", changestategroupevent__state="conclude").order_by('time')[:1]
        n.end_year = e[0].time.year if e else ""

        r = n.role_set.select_related().filter(name="chair") 
        chair = None 
        if r: 
            chair = r[0] 
        announcements = Message.objects.filter(related_groups=n).order_by('-time')
        for a in announcements:
            a.to_name = address_re.sub("", a.to)

        regimes.append(dict(chair=chair,
                            announcements=announcements,
                            group=n))

    regimes.sort(key=lambda x: x["group"].start_year, reverse=True)

    return direct_to_template(request,
                              "announcements/nomcomREDESIGN.html", 
                              { 'curr_chair' : regimes[0]["chair"],
                                'regimes' : regimes })

def message_detail(request, object_id):
    # restrict to nomcom announcements for the time being
    nomcoms = Group.objects.filter(acronym__startswith="nomcom").exclude(acronym="nomcom")
    m = get_object_or_404(Message, id=object_id,
                          related_groups__in=nomcoms)
    
    return direct_to_template(request,
                              "announcements/message_detail.html",
                              dict(message=m))
                                  
    
