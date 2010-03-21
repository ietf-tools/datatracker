# Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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
from ietf.idtracker.models import Area

register = template.Library()

area_short_names = {
    'ops':'Ops & Mgmt',
    'rai':'RAI'
    }

def get_short_name(area):
    if area.area_acronym.acronym in area_short_names:
        return area_short_names[area.area_acronym.acronym]
    else:
        area_name = area.area_acronym.name
        if area_name.endswith(" Area"):
            area_name = area_name[:-5]
        return area_name

class WgMenuNode(template.Node):
    def __init__(self):
        pass
    def render(self, context):
        x = cache.get('idrfc_wgmenu')
        if x:
            return x
        areas = [{'area':x, 'short_name':get_short_name(x)} for x in Area.active_areas()]
        x = loader.render_to_string('base_wgmenu.html', {'areas':areas})
        cache.set('idrfc_wgmenu', x, 30*60)
        return x
    
def do_wg_menu(parser, token):
    return WgMenuNode()

register.tag('wg_menu', do_wg_menu)
