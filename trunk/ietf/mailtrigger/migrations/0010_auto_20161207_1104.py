# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0009_review_sent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mailtrigger',
            name='cc',
            field=models.ManyToManyField(related_name='used_in_cc', to='mailtrigger.Recipient', blank=True),
        ),
        migrations.AlterField(
            model_name='mailtrigger',
            name='to',
            field=models.ManyToManyField(related_name='used_in_to', to='mailtrigger.Recipient', blank=True),
        ),
    ]
