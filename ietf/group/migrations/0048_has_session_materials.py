# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations

# Not adding team at this time - need to untangle the nonsession_materials mess first

types_to_change = [
    'program',
    'dir',
    'review',
]

def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    GroupFeatures.objects.filter(type__in=types_to_change).update(has_session_materials=True)

def reverse(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    GroupFeatures.objects.filter(type__in=types_to_change).update(has_session_materials=False)

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0047_ietfllc'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
