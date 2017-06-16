# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import django.db

def fill_in_docalias_relationship_names(apps, schema_editor):
    with django.db.connection.cursor() as cursor:
        cursor.execute("update ipr_iprdocrel join doc_docalias on doc_docalias.id = ipr_iprdocrel.document_id set ipr_iprdocrel.document_name = doc_docalias.name;")

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0004_iprdocrel_document_name'),
    ]

    operations = [
        migrations.RunPython(fill_in_docalias_relationship_names, noop)
    ]
