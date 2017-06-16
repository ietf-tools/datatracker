# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0032_reconstruct_bluesheet_docs_95through96'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='acknowledgements',
            field=models.TextField(help_text=b'Acknowledgements for use in meeting proceedings.  Use ReStructuredText markup.', blank=True),
            preserve_default=True,
        ),
    ]
