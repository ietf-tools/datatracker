# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('review', '0004_reviewsecretarysettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reviewersettings',
            name='remind_days_before_deadline',
            field=models.IntegerField(help_text=b"To get an email reminder in case you forget to do an assigned review, enter the number of days before review deadline you want to receive it. Clear the field if you don't want a reminder.", null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='reviewsecretarysettings',
            name='remind_days_before_deadline',
            field=models.IntegerField(help_text=b"To get an email reminder in case a reviewer forgets to do an assigned review, enter the number of days before review deadline you want to receive it. Clear the field if you don't want a reminder.", null=True, blank=True),
            preserve_default=True,
        ),
    ]
