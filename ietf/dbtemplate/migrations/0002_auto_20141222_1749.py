# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0001_initial'),
        ('name', '0001_initial'),
        ('dbtemplate', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dbtemplate',
            name='group',
            field=models.ForeignKey(blank=True, to='group.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='dbtemplate',
            name='type',
            field=models.ForeignKey(to='name.DBTemplateTypeName'),
            preserve_default=True,
        ),
    ]
