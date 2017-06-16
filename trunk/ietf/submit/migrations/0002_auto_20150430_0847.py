# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submit', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submission',
            name='authors',
            field=models.TextField(help_text=b'List of author names and emails, one author per line, e.g. "John Doe &lt;john@example.org&gt;".', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='submission',
            name='submitter',
            field=models.CharField(help_text=b'Name and email of submitter, e.g. "John Doe &lt;john@example.org&gt;".', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
