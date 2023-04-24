# Copyright The IETF Trust 2020, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0032_auto_20200824_1642'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='tombstone_for',
            field=models.ForeignKey(blank=True, help_text='This session is the tombstone for a session that was rescheduled', null=True, on_delete=django.db.models.deletion.CASCADE, to='meeting.Session'),
        ),
    ]
