# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oidc_provider', '0004_remove_userinfo'),
    ]

    operations = [
        migrations.AddField(
            model_name='token',
            name='refresh_token',
            field=models.CharField(max_length=255, unique=True, null=True),
            preserve_default=True,
        ),
    ]
