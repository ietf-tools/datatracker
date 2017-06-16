# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.nomcom.models


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0003_nomination_share_nominator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nomcom',
            name='public_key',
            field=models.FileField(storage=ietf.nomcom.models.NoLocationMigrationFileSystemStorage(location=None), null=True, upload_to=ietf.nomcom.models.upload_path_handler, blank=True),
            preserve_default=True,
        ),
    ]
