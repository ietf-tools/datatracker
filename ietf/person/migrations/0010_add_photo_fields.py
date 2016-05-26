# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.utils.storage


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0009_populate_biography'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='photo',
            field=models.ImageField(storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos/', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='person',
            name='photo_thumb',
            field=models.ImageField(storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos/', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='personhistory',
            name='photo',
            field=models.ImageField(storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos/', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='personhistory',
            name='photo_thumb',
            field=models.ImageField(storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos/', blank=True),
            preserve_default=True,
        ),
    ]
