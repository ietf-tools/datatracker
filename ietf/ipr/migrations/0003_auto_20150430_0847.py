# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0002_remove_legacy_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='genericiprdisclosure',
            name='holder_contact_info',
            field=models.TextField(help_text=b'Address, phone, etc.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='holderiprdisclosure',
            name='holder_contact_info',
            field=models.TextField(help_text=b'Address, phone, etc.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='compliant',
            field=models.BooleanField(default=True, verbose_name=b'Complies to RFC3979'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='notes',
            field=models.TextField(verbose_name=b'Additional notes', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='other_designations',
            field=models.CharField(max_length=255, verbose_name=b'Designations for other contributions', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='nondocspecificiprdisclosure',
            name='holder_contact_info',
            field=models.TextField(help_text=b'Address, phone, etc.', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='thirdpartyiprdisclosure',
            name='ietfer_contact_info',
            field=models.TextField(help_text=b'Address, phone, etc.', blank=True),
            preserve_default=True,
        ),
    ]
