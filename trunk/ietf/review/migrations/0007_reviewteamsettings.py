# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import ietf.review.models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0016_auto_20161013_1010'),
        ('group', '0009_auto_20150930_0758'),
        ('review', '0006_auto_20161209_0436'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewTeamSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('autosuggest', models.BooleanField(default=True, verbose_name=b'Automatically suggest possible review requests')),
                ('group', models.OneToOneField(to='group.Group')),
                ('review_results', models.ManyToManyField(default=ietf.review.models.get_default_review_results, to='name.ReviewResultName')),
                ('review_types', models.ManyToManyField(default=ietf.review.models.get_default_review_types, to='name.ReviewTypeName')),
            ],
            options={
                'verbose_name': 'Review team settings',
                'verbose_name_plural': 'Review team settings',
            },
        ),
    ]
