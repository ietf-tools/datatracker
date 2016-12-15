# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0008_populate_reviewteamsettings'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resultusedinreviewteam',
            name='result',
        ),
        migrations.RemoveField(
            model_name='resultusedinreviewteam',
            name='team',
        ),
        migrations.RemoveField(
            model_name='typeusedinreviewteam',
            name='team',
        ),
        migrations.RemoveField(
            model_name='typeusedinreviewteam',
            name='type',
        ),
        migrations.DeleteModel(
            name='ResultUsedInReviewTeam',
        ),
        migrations.DeleteModel(
            name='TypeUsedInReviewTeam',
        ),
    ]
