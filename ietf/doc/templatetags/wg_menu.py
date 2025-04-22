# Copyright The IETF Trust 2009-2023, All Rights Reserved

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

import debug    # pyflakes: ignore

from django import template
from django.template.loader import render_to_string
from django.db import models

from ietf.group.models import Group

register = template.Library()

parent_short_names = {
    "ops": "Ops & Management",
    "rai": "RAI",
    "iab": "IAB",
    "art": "Apps & Realtime",
    "ietfadminllc": "IETF LLC",
}

parents = Group.objects.filter(
    models.Q(type="area")
    | models.Q(type="irtf", acronym="irtf")
    | models.Q(acronym="iab")
    | models.Q(acronym="ietfadminllc")
    | models.Q(acronym="rfceditor"),
    state="active",
).order_by("type__order", "type_id", "acronym")


@register.simple_tag
def wg_menu(flavor):
    for p in parents:
        p.short_name = parent_short_names.get(p.acronym) or p.name
        if p.short_name.endswith(" Area"):
            p.short_name = p.short_name[: -len(" Area")]

        if p.type_id == "area":
            p.menu_url = "/wg/#" + p.acronym.upper()
        elif p.acronym == "irtf":
            p.menu_url = "/rg/"
        elif p.acronym == "iab":
            p.menu_url = "/program/"
        elif p.acronym == "ietfadminllc":
            p.menu_url = "/adm/"
        elif p.acronym == "rfceditor":
            p.menu_url = "/rfcedtyp/"

    return render_to_string(
        "base/menu_wg.html", {"parents": parents, "flavor": flavor}
    )
