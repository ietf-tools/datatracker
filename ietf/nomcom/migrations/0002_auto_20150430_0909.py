# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nomcom',
            name='reminder_interval',
            field=models.PositiveIntegerField(help_text=b'If the nomcom user sets the interval field then a cron command will send reminders to the nominees who have not responded using the following formula: (today - nomination_date) % interval == 0.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='nomcom',
            name='send_questionnaire',
            field=models.BooleanField(default=False, help_text=b'If you check this box, questionnaires are sent automatically after nominations.', verbose_name=b'Send questionnaires automatically'),
            preserve_default=True,
        ),
    ]
