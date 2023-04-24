# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.create(slug='iabasg', name='IAB ASG', verbose_name='IAB Administrative Support Group', desc='')

def reverse(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.filter(slug='iabasg').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0027_add_bofrequest'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
