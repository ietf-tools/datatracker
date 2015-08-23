# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0002_auto_20150430_0909'),
    ]

    operations = [
        migrations.AddField(
            model_name='nomination',
            name='share_nominator',
            field=models.BooleanField(default=False, help_text=b'Check this box to allow the NomCom to let the person you are nominating know that you were one of the people who nominated them. If you do not check this box, your name will be confidential and known only within NomCom.', verbose_name=b'Share nominator name with candidate'),
            preserve_default=True,
        ),
    ]
