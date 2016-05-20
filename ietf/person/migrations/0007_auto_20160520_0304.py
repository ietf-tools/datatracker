# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0006_auto_20160503_0937'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='address',
            field=models.TextField(help_text=b'Postal mailing address.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='affiliation',
            field=models.CharField(help_text=b'Employer, university, sponsor, etc.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='ascii',
            field=models.CharField(help_text=b'Name as rendered in ASCII (Latin, unaccented) characters.', max_length=255, verbose_name=b'Full Name (ASCII)'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='ascii_short',
            field=models.CharField(help_text=b'Example: A. Nonymous.  Fill in this with initials and surname only if taking the initials and surname of the ASCII name above produces an incorrect initials-only form. (Blank is OK).', max_length=32, null=True, verbose_name=b'Abbreviated Name (ASCII)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='name',
            field=models.CharField(help_text=b'Preferred form of name.', max_length=255, verbose_name=b'Full Name (Unicode)', db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='address',
            field=models.TextField(help_text=b'Postal mailing address.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='affiliation',
            field=models.CharField(help_text=b'Employer, university, sponsor, etc.', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='ascii',
            field=models.CharField(help_text=b'Name as rendered in ASCII (Latin, unaccented) characters.', max_length=255, verbose_name=b'Full Name (ASCII)'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='ascii_short',
            field=models.CharField(help_text=b'Example: A. Nonymous.  Fill in this with initials and surname only if taking the initials and surname of the ASCII name above produces an incorrect initials-only form. (Blank is OK).', max_length=32, null=True, verbose_name=b'Abbreviated Name (ASCII)', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='personhistory',
            name='name',
            field=models.CharField(help_text=b'Preferred form of name.', max_length=255, verbose_name=b'Full Name (Unicode)', db_index=True),
            preserve_default=True,
        ),
    ]
