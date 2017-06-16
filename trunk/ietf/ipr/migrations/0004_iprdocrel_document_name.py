# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0003_auto_20150430_0847'),
    ]

    operations = [
        migrations.AddField(
            model_name='iprdocrel',
            name='document_name',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
    ]
