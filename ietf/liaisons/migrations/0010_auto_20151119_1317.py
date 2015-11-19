# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0009_remove_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liaisonstatement',
            name='title',
            field=models.CharField(max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='liaisonstatement',
            name='to_contacts',
            field=models.CharField(help_text=b'Contacts at recipient group', max_length=255),
            preserve_default=True,
        ),
    ]
