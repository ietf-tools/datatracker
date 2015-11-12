# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def create_required_tags(apps, schema_editor):
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    for s in LiaisonStatement.objects.filter(deadline__isnull=False):
        if not s.tags.filter(slug='taken'):
            s.tags.add('required')
        
class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0007_auto_20151009_1220'),
    ]

    operations = [
        migrations.RunPython(create_required_tags),
    ]
