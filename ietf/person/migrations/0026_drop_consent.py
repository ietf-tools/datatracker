# Copyright The IETF Trust 2022, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0025_chat_and_polls_apikey'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalperson',
            name='consent',
        ),
        migrations.RemoveField(
            model_name='person',
            name='consent',
        ),
    ]
