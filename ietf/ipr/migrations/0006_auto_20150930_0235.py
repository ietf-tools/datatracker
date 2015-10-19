# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0005_auto_20150930_0227'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='iprdisclosurebase',
            name='docs',
        ),
        migrations.RemoveField(
            model_name='iprdocrel',
            name='document',
        ),
        migrations.RenameField(
            model_name='iprdocrel',
            old_name='document_name',
            new_name='document',
        ),
    ]
