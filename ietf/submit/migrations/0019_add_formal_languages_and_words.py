# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0021_add_formlang_names'),
        ('submit', '0018_fix_more_bad_submission_docevents'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='formal_languages',
            field=models.ManyToManyField(help_text=b'Formal languages used in document', to='name.FormalLanguageName', blank=True),
        ),
        migrations.AddField(
            model_name='submission',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
