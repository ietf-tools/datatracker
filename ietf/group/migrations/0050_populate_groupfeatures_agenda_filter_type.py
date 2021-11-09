# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    GroupFeatures = apps.get_model('group', 'GroupFeatures')

    # map AgendaFilterTypeName slug to group types - unlisted get 'none'
    filter_types = dict(
        # list previously hard coded in agenda view, plus 'review'
        normal={'wg', 'ag', 'rg', 'rag', 'iab', 'program', 'review'},
        heading={'area', 'ietf', 'irtf'},
        special={'team', 'adhoc'},
    )

    for ft, group_types in filter_types.items():
        for gf in GroupFeatures.objects.filter(type__slug__in=group_types):
            gf.agenda_filter_type_id = ft
            gf.save()


def reverse(apps, schema_editor):
    pass  # nothing to do, model will be deleted anyway


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0049_groupfeatures_agenda_filter_type'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
