# Copyright The IETF Trust 2023, All Rights Reserved
from django.db import migrations, models


def forward(apps, schema_editor):
    migrations.RemoveField(
        model_name='dochistory',
        name='order',
    )
    
    migrations.RemoveField(
        model_name='document',
        name='order',
    )

def reverse(apps, schema_editor):
    migrations.AddField(
        model_name='dochistory',
        name='order',
        field = models.IntegerField(default=1, blank=True),
    )

    migrations.AddField(
        model_name='document',
        name='order',
    )

class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0050_editorial_stream_states"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
