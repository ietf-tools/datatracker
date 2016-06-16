# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from ietf.mailinglists.models import List, Subscribed
from ietf.mailinglists.management.commands.import_mailman_listinfo import import_mailman_listinfo

def forward_mailman_import(apps, schema_editor):
    import_mailman_listinfo(verbosity=0)

def reverse_mailman_import(apps, schema_editor):
    List.objects.all().delete()
    Subscribed.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('mailinglists', '0002_list_subscribed_whitelisted'),
    ]

    operations = [
        migrations.RunPython(forward_mailman_import,reverse_mailman_import),

    ]
