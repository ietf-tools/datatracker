# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0010_auto_20151119_1317'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liaisonstatement',
            name='to_contacts',
            field=models.CharField(help_text=b'Contacts at recipient group', max_length=2000),
            preserve_default=True,
        ),
    ]
