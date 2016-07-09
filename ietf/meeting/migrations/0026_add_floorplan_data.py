# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

floors = [
    (1, "Berlin Intercontinental Floor 1",  1, 'floor/floorplan-96-berlin-intercontinental-floor-1.jpg'),
    (2, "Berlin Intercontinental Floor 2",  2, 'floor/floorplan-96-berlin-intercontinental-floor-2.jpg'),
    (3, "Berlin Intercontinental Floor 14",  14, 'floor/floorplan-96-berlin-intercontinental-floor-14.jpg'),
]

rooms = [
    ("Bellevue",                1,      176,	1348,	324,	1526),
    ("Bishop",                  2,      802,    1269,   890,    1390,),
    ("Charlottenburg I",        1,	374,	320,	528,	400),
    ("Charlottenburg II/III",	1,	374,	172,	528,	316),
    ("Chess",                   2,	802,	1150,	890,	1264),
    ("Dahlem",                  1,      201,    1035,   324,    1086),
    ("Glienicke",               1,	228,	1251,	324,	1310),
    ("Hugos 360",               3,	801,	1346,	976,	1509),
    ("Kaminzimmer",             1,	696,	820,	812,	1038),
    ("King",                    2,	802,	1389,	890,	1508),
    ("Koepenick I/II",          1,	370,	453,	458,	602),
    ("Koepenick III",           1,	456,    440,    540,    526),
    ("Lincke",                  2,	365,	111,	531,	171),
    ("Potsdam Foyer",           1,	918,    987,    1149,   1142),
    ("Potsdam I",               1,	1228,	790,	1550,	994),
    ("Potsdam I/III",           1,	1017,	792,	1550,	994),
    ("Potsdam II",              1,	1311,	1036,	1536,	1142),
    ("Potsdam III",             1,	1017,	792,	1228,	987),
    ("Rook",                    2,	915,	1150,	1004,	1269),
    ("Schinkel I/II",           2,      532,    222,    594,    360),
    ("Schinkel III",            2,      532,    112,    592,    222),
    ("Schoeneberg",             1,	369,	42,	534,	126),
    ("Tegel",                   1,	201,	1088,	326,	1184),
    ("Tiergarten",              1,	240,	612,	334,	780),
    ("Wintergarten/Pavillion",	1,	466,	1038,	711,	1504),
]

def forward(apps, schema_editor):
    FloorPlan = apps.get_model('meeting','FloorPlan')
    Room = apps.get_model('meeting','Room')
    Meeting = apps.get_model('meeting','Meeting')
    meeting = Meeting.objects.get(number='96')
    for item in floors:
        id, name, order, image = item
        f = FloorPlan(id=id, name=name, meeting=meeting, order=order, image=image)
        f.save()

    for item in rooms:
        name, floor_id, x1, y1, x2, y2 = item
        try:
            room = Room.objects.get(name=name, meeting=meeting)
            room.floorplan_id = floor_id
            room.x1 = x1
            room.y1 = y1
            room.x2 = x2
            room.y2 = y2
            room.save()
        except Room.DoesNotExist:
            import sys
            sys.stderr.write("\nNo such room: %s" % name)

def backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0025_add_floorplan_and_room_coordinates'),
    ]

    operations = [
        migrations.RunPython(forward,backward)
    ]
