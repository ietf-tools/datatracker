# Copyright The IETF Trust 2022 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.filter(slug='rfcedtyp').update(order=2, verbose_name='RFC Editor Group')

def reverse(apps, schema_editor):
    GroupTypeName = apps.get_model('name', 'GroupTypeName')
    GroupTypeName.objects.filter(slug='rfcedtyp').update(order=0, verbose_name='The RFC Editor')

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0040_remove_constraintname_editor_label'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
