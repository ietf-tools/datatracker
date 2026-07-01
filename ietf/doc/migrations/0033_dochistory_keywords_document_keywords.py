# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import ietf.doc.models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0032_remove_rfcauthor_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="dochistory",
            name="keywords",
            field=models.JSONField(
                default=list,
                max_length=1000,
                validators=[ietf.doc.models.validate_doc_keywords],
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="keywords",
            field=models.JSONField(
                default=list,
                max_length=1000,
                validators=[ietf.doc.models.validate_doc_keywords],
            ),
        ),
    ]
