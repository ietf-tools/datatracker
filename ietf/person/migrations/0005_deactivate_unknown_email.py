# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    Email = apps.get_model('person','Email')
    Email.objects.filter(address__startswith="unknown-email-",active=True).update(active=False)

def reverse(apps,schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0004_auto_20150308_0440'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
