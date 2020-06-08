# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    RoleName = apps.get_model('name','RoleName')
    RoleName.objects.get_or_create(slug='robot', name='Automation Robot', desc='A role for API access by external scripts or entities, such as the mail archive, registrations system, etc.', used=True, order=0)

def reverse(apps, schema_editor):
    RoleName = apps.get_model('name','RoleName')
    RoleName.objects.filter(slug='robot').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0011_constraintname_editor_label'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
