# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models


def forward(apps, schema_editor):
    AppealArtifactTypeName = apps.get_model("name", "AppealArtifactTypeName")
    for slug, name, desc, order in [
        ("appeal", "Appeal", "The content of an appeal", 1),
        (
            "appeal_with_response",
            "Response (with appeal included)",
            "The content of an appeal combined with the content of a response",
            2,
        ),
        ("response", "Response", "The content of a response to an appeal", 3),
        (
            "reply_to_response",
            "Reply to response",
            "The content of a reply to an appeal response",
            4,
        ),
        ("other_content", "Other content", "Other content related to an appeal", 5),
    ]:
        AppealArtifactTypeName.objects.create(
            slug=slug, name=name, desc=desc, order=order
        )


def reverse(apps, schema_editor):
    AppealArtifactTypeName = apps.get_model("name", "AppealArtifactTypeName")
    AppealArtifactTypeName.objects.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("name", "0006_feedbacktypename_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppealArtifactTypeName",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
                ("used", models.BooleanField(default=True)),
                ("order", models.IntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "name"],
                "abstract": False,
            },
        ),
        migrations.RunPython(forward, reverse),
    ]
