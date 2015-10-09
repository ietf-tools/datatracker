# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0006_remove_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liaisonstatement',
            name='from_groups',
            field=models.ManyToManyField(related_name='liaisonstatement_from_set', to='group.Group', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='liaisonstatement',
            name='to_groups',
            field=models.ManyToManyField(related_name='liaisonstatement_to_set', to='group.Group', blank=True),
            preserve_default=True,
        ),
    ]
