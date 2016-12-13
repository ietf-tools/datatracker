# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ipr', '0008_auto_20160720_0218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='genericiprdisclosure',
            name='holder_contact_email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name='holderiprdisclosure',
            name='holder_contact_email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name='holderiprdisclosure',
            name='ietfer_contact_email',
            field=models.EmailField(max_length=254, blank=True),
        ),
        migrations.AlterField(
            model_name='iprdisclosurebase',
            name='submitter_email',
            field=models.EmailField(max_length=254, blank=True),
        ),
        migrations.AlterField(
            model_name='nondocspecificiprdisclosure',
            name='holder_contact_email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name='thirdpartyiprdisclosure',
            name='ietfer_contact_email',
            field=models.EmailField(max_length=254),
        ),
    ]
