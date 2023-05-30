# Copyright The IETF Trust 2023, All Rights Reserved
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0002_auto_20230320_1222'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dochistory',
            name='order',
        ),
        migrations.RemoveField(
            model_name='document',
            name='order',
        ),
    ]
