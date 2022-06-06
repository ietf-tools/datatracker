# Copyright The IETF Trust 2022 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    Group.objects.create(
        acronym='editorial',
        name='Editorial Stream',
        state_id='active',
        type_id='editorial',
        parent=None,
    )
    templ = GroupFeatures.objects.get(type='rfcedtyp')
    templ.pk = None
    templ.type_id='editorial'
    templ.save()



def reverse(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    GroupFeatures.objects.filter(type='editorial').delete()
    Group.objects.filter(acronym='editorial').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0054_enable_delegation'),
        ('name', '0043_editorial_stream_grouptype'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
