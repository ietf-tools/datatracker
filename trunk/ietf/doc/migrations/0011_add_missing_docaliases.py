# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F

def reverse(apps, schema_editor):
    pass

def forward(apps, schema_editor):
    Document = apps.get_model('doc','Document')
    for doc in Document.objects.filter(type__in=['recording','liaison','liai-att']).exclude(docalias__name=F('name')):
        doc.docalias_set.create(name=doc.name)

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0010_auto_20150930_0251'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
