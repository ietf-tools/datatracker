# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0011_add_session_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='grouptypename',
            name='verbose_name',
            field=models.CharField(default=b'', max_length=255),
            preserve_default=True,
        ),
    ]
