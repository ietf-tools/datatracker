# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0023_add_country_continent_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffiliationAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('alias', models.CharField(help_text=b"Note that aliases will be matched case-insensitive and both before and after some clean-up.", max_length=255, unique=True)),
                ('name', models.CharField(max_length=255)),
            ],
            options={'verbose_name_plural': 'affiliation aliases'},
        ),
        migrations.CreateModel(
            name='AffiliationIgnoredEnding',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ending', models.CharField(help_text=b"Regexp with ending, e.g. 'Inc\\.?' - remember to escape .!", max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='CountryAlias',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('alias', models.CharField(help_text=b"Note that lower-case aliases are matched case-insensitive while aliases with at least one uppercase letter is matched case-sensitive. So 'United States' is best entered as 'united states' so it both matches 'United States' and 'United states' and 'UNITED STATES', whereas 'US' is best entered as 'US' so it doesn't accidentally match an ordinary word like 'us'.", max_length=255)),
                ('country', models.ForeignKey(to='name.CountryName', max_length=255)),
            ],
            options={'verbose_name_plural': 'country aliases'},
        ),
    ]
