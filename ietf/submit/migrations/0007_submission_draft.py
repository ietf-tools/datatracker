# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0012_auto_20160207_0537'),
        ('submit', '0006_remove_submission_idnits_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='draft',
            field=models.ForeignKey(null=True, blank=True, to='doc.Document'),
            preserve_default=True,
        ),
    ]
