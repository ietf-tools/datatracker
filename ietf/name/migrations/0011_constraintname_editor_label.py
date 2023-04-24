# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0010_timerangename'),
    ]

    def fill_in_editor_labels(apps, schema_editor):
        ConstraintName = apps.get_model('name', 'ConstraintName')
        for cn in ConstraintName.objects.all():
            cn.editor_label = {
                'conflict': "(1)",
                'conflic2': "(2)",
                'conflic3': "(3)",
                'bethere': "(person)",
            }.get(cn.slug, cn.slug)
            cn.save()

    def noop(apps, schema_editor):
        pass

    operations = [
        migrations.AddField(
            model_name='constraintname',
            name='editor_label',
            field=models.CharField(blank=True, help_text='Very short label for producing warnings inline in the sessions in the schedule editor.', max_length=32),
        ),
        migrations.RunPython(fill_in_editor_labels, noop, elidable=True),
    ]
