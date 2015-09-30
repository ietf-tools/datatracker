# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0005_auto_20150721_0230'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dochistory',
            name='related',
        ),
        migrations.AddField(
            model_name='relateddochistory',
            name='target_name',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='relateddocument',
            name='target_name',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
    ]
