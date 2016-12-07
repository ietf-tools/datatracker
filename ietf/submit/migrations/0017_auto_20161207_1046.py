# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0016_fix_duplicate_upload_docevents'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissioncheck',
            name='time',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
