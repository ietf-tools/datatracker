# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oidc_provider', '0002_userconsent'),
    ]

    operations = [
        migrations.AddField(
            model_name='code',
            name='nonce',
            field=models.CharField(default=b'', max_length=255, blank=True),
        ),
    ]
