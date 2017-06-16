# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

rooms = [
        ("Bellevue",                 "http://ietf96streaming.dnsalias.net/ietf/ietf961.m3u"),
        ("Charlottenburg I",         "http://ietf96streaming.dnsalias.net/ietf/ietf962.m3u"),
        ("Charlottenburg II/III",    "http://ietf96streaming.dnsalias.net/ietf/ietf963.m3u"),
        ("Lincke",                   "http://ietf96streaming.dnsalias.net/ietf/ietf964.m3u"),
        ("Potsdam I",                "http://ietf96streaming.dnsalias.net/ietf/ietf965.m3u"),
        ("Potsdam II",               "http://ietf96streaming.dnsalias.net/ietf/ietf966.m3u"),
        ("Potsdam III",              "http://ietf96streaming.dnsalias.net/ietf/ietf967.m3u"),
        ("Schoeneberg",              "http://ietf96streaming.dnsalias.net/ietf/ietf968.m3u"),
        ("Tiergarten",               "http://ietf96streaming.dnsalias.net/ietf/ietf969.m3u"),
]

def forward(apps, schema_editor):
    Room = apps.get_model('meeting','Room')
    Meeting = apps.get_model('meeting','Meeting')
    UrlResource = apps.get_model('meeting','UrlResource')
    RoomResourceName = apps.get_model('name','RoomResourceName')

    meeting = Meeting.objects.get(number='96')
    
    audiostream, _ = RoomResourceName.objects.get_or_create(slug='audiostream', name='Audio Stream', desc='Audio streaming support')

    for item in rooms:
        name, url = item
        try:
            room = Room.objects.get(name=name, meeting=meeting)
            urlres, _ = UrlResource.objects.get_or_create(name=audiostream, room=room, url=url)
        except Room.DoesNotExist:
            import sys
            sys.stderr.write("\nNo such room: %s" % name)

def backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0027_urlresource'),
    ]

    operations = [
        migrations.RunPython(forward,backward)
    ]
