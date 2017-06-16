# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0008_populate_reviewteamsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewrequest',
            name='comment',
            field=models.TextField(default=b'', help_text=b'Provide any additional information to show to the review team secretary and reviewer', max_length=2048, verbose_name=b"Requester's comments and instructions", blank=True),
        ),
    ]
