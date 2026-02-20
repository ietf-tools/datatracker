# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0030_alter_dochistory_title_alter_document_title"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rfcauthor",
            name="email",
        ),
    ]
