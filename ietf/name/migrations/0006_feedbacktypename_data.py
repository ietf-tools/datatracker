# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    FeedbackTypeName = apps.get_model("name", "FeedbackTypeName")
    FeedbackTypeName.objects.create(slug="obe", name="Overcome by events")
    for slug, legend, order in (
        ('comment', 'C', 1),
        ('nomina',  'N', 2),
        ('questio', 'Q', 3),
        ('obe',     'O', 4),
        ('junk',    'J', 5),
        ('read',    'R', 6),
    ):
        ft = FeedbackTypeName.objects.get(slug=slug)
        ft.legend = legend
        ft.order = order
        ft.save()

def reverse(apps, schema_editor):
    FeedbackTypeName = apps.get_model("name", "FeedbackTypeName")
    FeedbackTypeName.objects.filter(slug="obe").delete()
    for ft in FeedbackTypeName.objects.all():
        ft.legend = ""
        ft.order = 0
        ft.save()

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0005_feedbacktypename_schema"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
