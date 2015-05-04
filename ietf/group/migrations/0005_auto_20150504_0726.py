# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def create_iab_roles(apps, schema_editor):
    Role = apps.get_model('group','Role')
    Group = apps.get_model('group','Group')
    Person = apps.get_model('person','Person')

    iab = Group.objects.get(acronym='iab')

    iab_names = [
                  'Jari Arkko',
                  'Mary Barnes',
                  'Marc Blanchet',
                  'Ralph Droms',
                  'Ted Hardie',
                  'Joe Hildebrand',
                  'Russ Housley',
                  'Erik Nordmark',
                  'Robert Sparks',
                  'Andrew Sullivan',
                  'Dave Thaler',
                  'Brian Trammell',
                  'Suzanne Woolf',
                ]
   
    for name in iab_names:
        person = Person.objects.get(name=name)
        person.role_set.add(Role(name_id='member',group=iab,person=person,email_id=person.email_set.filter(active=True).order_by('-time').first().address))


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0004_auto_20150430_0847'),
    ]

    operations = [
        migrations.RunPython(create_iab_roles),
    ]
