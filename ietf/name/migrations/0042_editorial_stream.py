# Copyright The IETF Trust 2022 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    StreamName = apps.get_model('name', 'StreamName')
    StreamName.objects.create(
        slug = 'editorial',
        name = 'Editorial',
        desc = 'Editorial',
        used = True,
        order = 5,
    )
    StreamName.objects.filter(slug='legacy').update(order=6)


def reverse(apps, schema_editor):
    StreamName = apps.get_model('name', 'StreamName')
    StreamName.objects.filter(slug='editorial').delete()
    StreamName.objects.filter(slug='legacy').update(order=5)

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0041_update_rfcedtyp'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
