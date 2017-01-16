# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0017_formallanguagename'),
        ('doc', '0019_auto_20161207_1036'),
    ]

    operations = [
        migrations.AddField(
            model_name='dochistory',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='document',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='dochistory',
            name='formal_languages',
            field=models.ManyToManyField(help_text=b'Formal languages used in document', to='name.FormalLanguageName', blank=True),
        ),
        migrations.AddField(
            model_name='document',
            name='formal_languages',
            field=models.ManyToManyField(help_text=b'Formal languages used in document', to='name.FormalLanguageName', blank=True),
        ),
    ]
