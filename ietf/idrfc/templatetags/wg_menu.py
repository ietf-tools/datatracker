# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from django import template
from django.core.cache import cache
from django.template import loader
from ietf.idtracker.models import IETFWG, Area

register = template.Library()

area_short_names = {
    'ops':'Ops & Mgmt',
    'rai':'Real-time Apps & Infra'
    }

def get_wgs():
    wgs = IETFWG.objects.filter(group_type__type='WG').filter(status__status='Active').select_related().order_by('acronym.acronym')
    areas = []
    for a in Area.objects.filter(status__status='Active').select_related().order_by('acronym.acronym'):
        wglist = []
        for w in wgs:
            if w.area.area == a:
                wglist.append(w)
        if len(wglist) > 0:
            if a.area_acronym.acronym in area_short_names:
                area_name = area_short_names[a.area_acronym.acronym]
            else:
                area_name = a.area_acronym.name
                if area_name.endswith(" Area"):
                    area_name = area_name[:-5]
            areas.append({'areaAcronym':a.area_acronym.acronym, 'areaName':area_name, 'areaObj':a, 'wgs':wglist})
    return areas

class WgMenuNode(template.Node):
    def __init__(self):
        pass
    def render(self, context):
        x = cache.get('idrfc_wgmenu')
        if x:
            return x
        areas = get_wgs()
        x = loader.render_to_string('idrfc/base_wgmenu.html', {'areas':areas})
        cache.set('idrfc_wgmenu', x, 30*60)
        return x
    
def do_wg_menu(parser, token):
    return WgMenuNode()

register.tag('wg_menu', do_wg_menu)
