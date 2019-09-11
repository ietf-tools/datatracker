# Copyright The IETF Trust 2019, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    State = apps.get_model('doc','State')
    State.objects.get_or_create(type_id='draft-rfceditor', slug='tooling-issue', name='TI',
                         desc='Tooling Issue; an update is needed to one or more of the tools in the publication pipeline before this document can be published')

def reverse(apps, schema_editor):
    State = apps.get_model('doc','State')
    State.objects.filter(type_id='draft-rfceditor', slug='tooling-issue').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0025_ianaexpertdocevent'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
