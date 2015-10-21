# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0007_populate_liaison_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctypename',
            name='prefix',
            field=models.CharField(default=b'', max_length=16),
            preserve_default=True,
        ),
    ]
