# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0033_populate_agendafiltertypename'),
        ('group', '0049_auto_20211019_1136'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupfeatures',
            name='agenda_filter_type',
            field=models.ForeignKey(default='none', on_delete=django.db.models.deletion.PROTECT, to='name.AgendaFilterTypeName'),
        ),
    ]
