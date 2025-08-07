# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oidc_provider', '0005_token_refresh_token'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='userconsent',
            unique_together=set([('user', 'client')]),
        ),
    ]
