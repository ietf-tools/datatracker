# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.utils.storage


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0011_populate_photos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='biography',
            field=models.TextField(help_text=b'Short biography for use on leadership pages. Use plain text or reStructuredText markup.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='photo',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='photo_thumb',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='biography',
            field=models.TextField(help_text=b'Short biography for use on leadership pages. Use plain text or reStructuredText markup.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='photo',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='photo_thumb',
            field=models.ImageField(default=None, storage=ietf.utils.storage.NoLocationMigrationFileSystemStorage(location=None), upload_to=b'photos', blank=True),
            preserve_default=True,
        ),
    ]
