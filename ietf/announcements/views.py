# Copyright The IETF Trust 2007, All Rights Reserved

from django.views.generic.simple import direct_to_template
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q

import re

from ietf.idtracker.models import ChairsHistory
from ietf.idtracker.models import Role
from ietf.announcements.models import Announcement
from ietf.group.models import Group, GroupEvent
from ietf.message.models import Message

def nomcom(request):
    curr_chair       = (ChairsHistory.objects.
                        get(chair_type=Role.NOMCOM_CHAIR, present_chair='1'))

    all_chairs       = (ChairsHistory.objects.all().
                        filter(chair_type='3',start_year__gt = 2003).
                        order_by('-start_year'))

    nomcom_announcements = Announcement.objects.all().filter(nomcom=1)

    regimes = []

    for chair in all_chairs:
        chair_announcements = (nomcom_announcements.filter(nomcom_chair=chair).
                               order_by('-announced_date','-announced_time'))
        regimes = regimes + [{'chair': chair, 
                              'announcements' : chair_announcements }]

    return direct_to_template(request,
                              "announcements/nomcom.html", 
                              { 'curr_chair' : curr_chair,
                                'regimes' : regimes })

def nomcomREDESIGN(request):
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
        

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    nomcom = nomcomREDESIGN


def message_detail(request, object_id):
    # restrict to nomcom announcements for the time being
    nomcoms = Group.objects.filter(acronym__startswith="nomcom").exclude(acronym="nomcom")
    m = get_object_or_404(Message, id=object_id,
                          related_groups__in=nomcoms)
    
    return direct_to_template(request,
                              "announcements/message_detail.html",
                              dict(message=m))
                                  
    
