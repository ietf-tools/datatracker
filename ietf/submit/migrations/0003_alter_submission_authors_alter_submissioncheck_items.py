# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


def forward(apps, schema_editor):
    JSON_ENCODED_NULL = r"\u0000"
    NULL = "\x00"
    NUL_SYMBOL = "\u2400"  # Unicode single-char "NUL" symbol 
    
    Submission = apps.get_model("submit", "Submission")
    # The qs filter sees the serialized JSON string...
    null_in_authors = Submission.objects.filter(authors__contains=JSON_ENCODED_NULL)
    for submission in null_in_authors:
        # submission.authors is now deserialized into Python objects
        for author in submission.authors:
            for k in author:
                author[k] = author[k].replace(NULL, NUL_SYMBOL)
        submission.save()


def reverse(apps, schema_editor):
    pass  # don't restore invalid data


class Migration(migrations.Migration):
    dependencies = [
        ("submit", "0002_alter_submission_xml_version"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
        migrations.AlterField(
            model_name="submission",
            name="authors",
            field=models.JSONField(
                default=list,
                help_text="List of authors with name, email, affiliation and country.",
            ),
        ),
        migrations.AlterField(
            model_name="submissioncheck",
            name="items",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
