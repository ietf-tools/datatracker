# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='iprcontact',
            name='ipr',
        ),
        migrations.DeleteModel(
            name='IprContact',
        ),
        migrations.RemoveField(
            model_name='iprdocalias',
            name='doc_alias',
        ),
        migrations.RemoveField(
            model_name='iprdocalias',
            name='ipr',
        ),
        migrations.DeleteModel(
            name='IprDocAlias',
        ),
        migrations.RemoveField(
            model_name='iprnotification',
            name='ipr',
        ),
        migrations.DeleteModel(
            name='IprNotification',
        ),
        migrations.RemoveField(
            model_name='iprupdate',
            name='ipr',
        ),
        migrations.RemoveField(
            model_name='iprupdate',
            name='updated',
        ),
        migrations.DeleteModel(
            name='IprDetail',
        ),
        migrations.DeleteModel(
            name='IprUpdate',
        ),
    ]
