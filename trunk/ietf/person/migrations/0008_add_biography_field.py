# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0007_auto_20160520_0304'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='biography',
            field=models.TextField(help_text=b'Short biography for use on leadership pages.', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='personhistory',
            name='biography',
            field=models.TextField(help_text=b'Short biography for use on leadership pages.', blank=True),
            preserve_default=True,
        ),
    ]
