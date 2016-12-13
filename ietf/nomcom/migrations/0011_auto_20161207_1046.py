# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0010_nominee_person'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feedback',
            name='author',
            field=models.EmailField(max_length=254, verbose_name=b'Author', blank=True),
        ),
        migrations.AlterField(
            model_name='feedback',
            name='nominees',
            field=models.ManyToManyField(to='nomcom.Nominee', blank=True),
        ),
        migrations.AlterField(
            model_name='feedback',
            name='positions',
            field=models.ManyToManyField(to='nomcom.Position', blank=True),
        ),
        migrations.AlterField(
            model_name='nomination',
            name='nominator_email',
            field=models.EmailField(max_length=254, verbose_name=b'Nominator Email', blank=True),
        ),
    ]
