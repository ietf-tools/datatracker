# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mailinglists', '0003_import_subscribers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subscribed',
            options={'verbose_name_plural': 'Subscribed'},
        ),
        migrations.AlterModelOptions(
            name='whitelisted',
            options={'verbose_name_plural': 'Whitelisted'},
        ),
    ]
