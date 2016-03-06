# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0005_auto_20160227_0809'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submission',
            name='idnits_message',
        ),
    ]
