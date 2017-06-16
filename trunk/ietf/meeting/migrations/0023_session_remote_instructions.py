# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0022_auto_20160505_0523'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='remote_instructions',
            field=models.CharField(max_length=1024, blank=True),
            preserve_default=True,
        ),
    ]
