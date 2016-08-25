# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dbtemplate', '0002_auto_20141222_1749'),
        ('meeting', '0033_add_meeting_acknowlegements'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='overview',
            field=models.ForeignKey(related_name='overview', editable=False, to='dbtemplate.DBTemplate', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='meeting',
            name='acknowledgements',
            field=models.TextField(help_text=b'Acknowledgements for use in meeting proceedings.  Use ReStructuredText markup.', blank=True),
            preserve_default=True,
        ),
    ]
