# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0036_add_order_to_sessionpresentation'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='sessionpresentation',
            options={'ordering': ('order',)},
        ),
    ]
