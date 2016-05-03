# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0005_deactivate_unknown_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='ascii',
            field=models.CharField(max_length=255, verbose_name=b'Full Name (ASCII)'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='ascii_short',
            field=models.CharField(max_length=32, null=True, verbose_name=b'Abbreviated Name (ASCII)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='name',
            field=models.CharField(max_length=255, verbose_name=b'Full Name (Unicode)', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='ascii',
            field=models.CharField(max_length=255, verbose_name=b'Full Name (ASCII)'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='ascii_short',
            field=models.CharField(max_length=32, null=True, verbose_name=b'Abbreviated Name (ASCII)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='name',
            field=models.CharField(max_length=255, verbose_name=b'Full Name (Unicode)', db_index=True),
            preserve_default=True,
        ),
    ]
