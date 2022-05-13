# Copyright The IETF Trust 2022 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.create(
        slug = 'editorial',
        name = 'Editorial',
        desc = 'Editorial Stream Group',
        used = True,
    )

def reverse(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.filter(slug='editorial').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0042_editorial_stream'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
