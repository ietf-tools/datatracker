# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def populate_names(apps, schema_editor):
    SessionStatusName = apps.get_model("name", "SessionStatusName")
    SessionStatusName.objects.create(slug="scheda",name="Scheduled - Announcement to be sent")
    SessionStatusName.objects.create(slug="canceledpa",name="Cancelled - Pre Announcement")

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0010_new_liaison_names'),
    ]

    operations = [
        migrations.RunPython(populate_names),
    ]
