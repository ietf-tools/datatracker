# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    DocTagName = apps.get_model('name','DocTagName')
    DocTagName.objects.get_or_create(slug='verified-errata', name='Has verified errata', desc='', used=True, order=0)

def reverse(apps, schema_editor):
    DocTagName = apps.get_model('name','DocTagName')
    DocTagName.objects.filter(slug='verified-errata').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0008_reviewerqueuepolicyname'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
