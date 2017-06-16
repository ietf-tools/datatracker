# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0005_migrate_groups'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='action_taken',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='approved',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='from_group',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='modified',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='related_to',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='reply_to',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='submitted',
        ),
        migrations.RemoveField(
            model_name='liaisonstatement',
            name='to_group',
        ),
        #migrations.RemoveField(
        #    model_name='liaisonstatement',
        #    name='from_contact',
        #),
    ]
