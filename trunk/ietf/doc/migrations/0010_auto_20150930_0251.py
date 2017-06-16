# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0009_auto_20150930_0248'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relateddochistory',
            name='target',
            field=models.ForeignKey(related_name='reversely_related_document_history_set', to='doc.DocAlias'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='relateddocument',
            name='target',
            field=models.ForeignKey(to='doc.DocAlias'),
            preserve_default=True,
        ),
    ]
