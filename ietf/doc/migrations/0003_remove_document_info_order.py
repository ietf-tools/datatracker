# Copyright The IETF Trust 2023, All Rights Reserved
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0003_remove_document_info_order'),
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
