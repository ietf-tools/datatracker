# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0008_data_for_submission_draft_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissioncheck',
            name='symbol',
            field=models.CharField(default=b'', max_length=64),
            preserve_default=True,
        ),
    ]
