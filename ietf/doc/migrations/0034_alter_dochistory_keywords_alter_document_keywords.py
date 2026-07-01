# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import ietf.doc.models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0033_dochistory_keywords_document_keywords"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dochistory",
            name="keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                max_length=1000,
                validators=[ietf.doc.models.validate_doc_keywords],
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                max_length=1000,
                validators=[ietf.doc.models.validate_doc_keywords],
            ),
        ),
    ]
