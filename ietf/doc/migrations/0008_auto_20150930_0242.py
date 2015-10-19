# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0007_auto_20150929_0840'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='relateddochistory',
            name='target',
        ),
        migrations.RenameField(
            model_name='relateddochistory',
            old_name='target_name',
            new_name='target',
        ),
        migrations.RemoveField(
            model_name='relateddocument',
            name='target',
        ),
        migrations.RenameField(
            model_name='relateddocument',
            old_name='target_name',
            new_name='target',
        ),
    ]
