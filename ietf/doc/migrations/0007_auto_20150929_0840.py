# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import django.db

def fill_in_docalias_relationship_names(apps, schema_editor):
    with django.db.connection.cursor() as cursor:
        cursor.execute("update doc_relateddocument join doc_docalias on doc_docalias.id = doc_relateddocument.target_id set doc_relateddocument.target_name = doc_docalias.name;")
        cursor.execute("update doc_relateddochistory join doc_docalias on doc_docalias.id = doc_relateddochistory.target_id set doc_relateddochistory.target_name = doc_docalias.name;")

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0006_auto_20150929_0828'),
    ]

    operations = [
        migrations.RunPython(fill_in_docalias_relationship_names, noop)
    ]
