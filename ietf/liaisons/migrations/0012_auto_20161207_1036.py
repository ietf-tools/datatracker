# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0011_auto_20161013_1034'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liaisonstatement',
            name='tags',
            field=models.ManyToManyField(to='name.LiaisonStatementTagName', blank=True),
        ),
        migrations.AlterField(
            model_name='liaisonstatementgroupcontacts',
            name='group',
            field=models.ForeignKey(null=True, to='group.Group', unique=True),
        ),
    ]
