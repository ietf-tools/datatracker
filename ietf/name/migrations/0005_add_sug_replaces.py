# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_possibly_replaces(apps, schema_editor):

        DocRelationshipName = apps.get_model("name","DocRelationshipName")
        DocRelationshipName.objects.create(slug='possibly-replaces',name='Possibly Replaces',revname='Possibly Replaced By')

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0004_auto_20150318_1140'),
    ]

    operations = [
        migrations.RunPython(add_possibly_replaces)
    ]
