# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    Group = apps.get_model('group', 'Group')

    # Copy program to iabasg
    feat = GroupFeatures.objects.get(pk='program')
    feat.pk = 'iabasg'
    feat.save()
    feat.parent_types.add('ietf')

    # List provided by Cindy on 30Aug2021
    Group.objects.filter(acronym__in=['iana-evolution','iproc','liaison-oversight','ietfiana','plenary-planning','rfcedprog']).update(type_id='iabasg')

    Group.objects.filter(acronym='model-t').update(parent=Group.objects.get(acronym='iab'))

def reverse(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')
    Group = apps.get_model('group', 'Group')
    Group.objects.filter(type_id='iabasg').update(type_id='program')
    # Intentionally not removing the parent of model-t
    GroupFeatures.objects.filter(pk='iabasg').delete()



class Migration(migrations.Migration):

    dependencies = [
        ('group', '0044_populate_groupfeatures_parent_type_fields'),
        ('name', '0028_iabasg'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
