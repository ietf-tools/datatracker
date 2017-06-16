# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def addNames(apps,schema_editor):
    GroupTypeName = apps.get_model('name','GroupTypeName')
    RoleName = apps.get_model('name','RoleName')

    GroupTypeName.objects.create(slug='program', name='Program', desc='Program', used=True, order=0)
    RoleName.objects.create(slug='lead', name='Lead', desc='Lead member (such as the Lead of an IAB program)', used=True, order=0)

def removeNames(apps,schema_editor):
    GroupTypeName = apps.get_model('name','GroupTypeName')
    RoleName = apps.get_model('name','RoleName')
    GroupTypeName.objects.filter(slug='program').delete()
    RoleName.objects.filter(slug='program').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0017_add_role_name_trac_admin'),
    ]

    operations = [
        migrations.RunPython(addNames,removeNames)
    ]
