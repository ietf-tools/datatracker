# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forwards(apps, schema_editor):
    RoleName = apps.get_model('name', 'RoleName')
    RoleName.objects.create(slug='trac-admin', name='Trac Admin',
        desc='Assigned permission TRAC_ADMIN in datatracker-managed Trac Wiki instances',
        used=True)
    
def backwards(apps, schema_editor):
    RoleName = apps.get_model('name', 'RoleName')
    RoleName.objects.filter(slug='trac-admin').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0016_auto_20161013_1010'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
