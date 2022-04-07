# Copyright The IETF Trust 2022 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group','GroupFeatures')
    for type_id in ('dir', 'iabasg', 'program', 'review', 'team'):
        f = GroupFeatures.objects.get(type_id=type_id)
        if 'delegate' not in f.groupman_roles:
            f.groupman_roles.append('delegate')
            f.save()
    for type_id in ('adhoc', 'ag', 'iesg', 'irtf', 'ise', 'rag', 'dir', 'iabasg', 'program', 'review'):
        f = GroupFeatures.objects.get(type_id=type_id)
        if 'delegate' not in f.default_used_roles:
            f.default_used_roles.append('delegate')
            f.save()

def reverse (apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0053_populate_groupfeatures_session_purposes'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
