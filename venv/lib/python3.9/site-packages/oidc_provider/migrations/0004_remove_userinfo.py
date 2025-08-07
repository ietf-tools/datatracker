# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oidc_provider', '0003_code_nonce'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userinfo',
            name='user',
        ),
        migrations.DeleteModel(
            name='UserInfo',
        ),
    ]
