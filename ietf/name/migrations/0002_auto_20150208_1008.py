# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_bluesheet_names(apps, schema_editor):
    DocTypeName = apps.get_model('name', 'DocTypeName')
    StateType   = apps.get_model('doc', 'StateType')
    State       = apps.get_model('doc', 'State')
    #
    DocTypeName.objects.create(slug="bluesheets",name="Bluesheets")
    StateType.objects.create(slug='bluesheets',label='State')
    State.objects.create(type_id='bluesheets',slug='active',name='Active')
    State.objects.create(type_id='bluesheets',slug='deleted',name='Deleted')

def del_bluesheet_names(apps, schema_editor):
    DocTypeName = apps.get_model('name', 'DocTypeName')
    StateType   = apps.get_model('doc', 'StateType')
    State       = apps.get_model('doc', 'State')
    #
    DocTypeName.objects.filter(slug="bluesheets").delete()
    StateType.objects.filter(slug='bluesheets').delete()
    State.objects.filter(type_id='bluesheets').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0001_initial'),
        ('doc', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_bluesheet_names, del_bluesheet_names),
    ]
