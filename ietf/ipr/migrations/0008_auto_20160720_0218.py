# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0007_auto_20150930_0258'),
    ]

    operations = [
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='submitter_email',
            field=models.EmailField(max_length=75, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='submitter_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
