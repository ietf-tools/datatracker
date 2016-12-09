# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import ietf.utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0005_auto_20161130_0628'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reviewersettings',
            name='filter_re',
            field=models.CharField(blank=True, help_text=b'Draft names matching this regular expression should not be assigned', max_length=255, verbose_name=b'Filter regexp', validators=[ietf.utils.validators.RegexStringValidator()]),
            preserve_default=True,
        ),
    ]
