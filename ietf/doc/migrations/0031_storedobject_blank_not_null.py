# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0030_alter_dochistory_title_alter_document_title"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storedobject",
            name="doc_name",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="storedobject",
            name="doc_rev",
            field=models.CharField(blank=True, default="", max_length=16),
            preserve_default=False,
        ),
    ]
