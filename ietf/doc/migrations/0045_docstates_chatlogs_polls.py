# Copyright The IETF Trust 2022, All Rights Reserved
from django.db import migrations

def forward(apps, shema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")
    for slug in ("chatlog", "polls"):     
        StateType.objects.create(slug=slug, label="State")
        for state_slug in ("active", "deleted"):
            State.objects.create(
                type_id = slug,
                slug = state_slug,
                name = state_slug.capitalize(),
                used = True,
                desc = "",
                order = 0,
            )

def reverse(apps, shema_editor):
    StateType = apps.get_model("doc", "StateType")
    State = apps.get_model("doc", "State")
    State.objects.filter(type_id__in=("chatlog", "polls")).delete()
    StateType.objects.filter(slug__in=("chatlog", "polls")).delete()  

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0044_procmaterials_states'),
        ('name', '0045_polls_and_chatlogs'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
