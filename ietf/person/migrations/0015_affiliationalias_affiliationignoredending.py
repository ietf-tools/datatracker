# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0014_auto_20160613_0751'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffiliationAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('alias', models.CharField(help_text=b'Note that aliases are matched without regarding case.', max_length=255)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='AffiliationIgnoredEnding',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ending', models.CharField(max_length=255)),
            ],
        ),
    ]
