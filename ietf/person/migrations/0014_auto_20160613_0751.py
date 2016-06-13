# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.utils.storage


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0013_add_plain_name_aliases'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='photo',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photo', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='photo_thumb',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photo', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='photo',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photo', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='photo_thumb',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photo', blank=True),
            preserve_default=True,
        ),
    ]
