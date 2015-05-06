# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def add_91_room_functional_names(apps, schema_editor):

    map = { 
           'Hibiscus':          'Breakout 3',
           'South Pacific 2':   'Meeting Room #6',
           'South Pacific 1':   'Terminal Room',
           'Coral 1':           'Breakout 4',
           'Coral 2':           'Breakout 5',
           'Coral 5':           'Breakout 6',
           'Coral 4':           'Breakout 7',
           'Coral 3':           'Breakout 8',
           'Great Lawn':        'Welcome Reception',
           'Rainbow Suite':     'Not Used',
           'Lehua Suite':       'Breakout 1',
           'Kahili':            'Breakout 2',
           'Rainbow Suite 1/2': 'Meeting Room #2 (IESG Meeting Room)',
           'Village Green':     'Meet and Greet',
           'South Pacific 3':   'Meeting Room #4 (IAOC/IAD Office)',
           'Rainbow Suite 3':   'Meeting Room #7',
           'Rainbow Suite 2/3': 'ISOC Dinner',
           'South Pacific 3/4': 'ISOC AC Meeting',
           'Iolani 6/7':        'Meeting Room #5 (NomCom Office)',
           'Sea Pearl 1/2':     'Reception',
           'Sea Pearl 2':       'Meeting Room #1 (IAB Meeting Room)',
           'Coral Lounge':      'Registration Area and Breaks',
           'Tiare Suite':       'Meeting Room #8 (RFC Office)',
          }

    Room  = apps.get_model('meeting', 'Room')

    for name,functional_name in map.items():
        Room.objects.filter(meeting__number=91,name=name).update(functional_name=functional_name)

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0009_room_functional_name'),
    ]

    operations = [
        migrations.RunPython(add_91_room_functional_names),
    ]

