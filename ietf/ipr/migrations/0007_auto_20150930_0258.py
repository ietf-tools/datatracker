# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0010_auto_20150930_0251'),
        ('ipr', '0006_auto_20150930_0235'),
    ]

    operations = [
        migrations.AddField(
            model_name='iprdisclosurebase',
            name='docs',
            field=models.ManyToManyField(to='doc.DocAlias', through='ipr.IprDocRel'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iprdocrel',
            name='document',
            field=models.ForeignKey(to='doc.DocAlias'),
            preserve_default=True,
        ),
    ]
