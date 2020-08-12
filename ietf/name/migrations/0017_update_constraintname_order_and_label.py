# Copyright The IETF Trust 2020, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('name', '0016_add_research_area_groups'),
    ]

    def update_editor_labels(apps, schema_editor):
        ConstraintName = apps.get_model('name', 'ConstraintName')
        for cn in ConstraintName.objects.all():
            cn.editor_label = {
                'bethere': "<i class=\"fa fa-user-o\"></i>{count}",
                'wg_adjacent': "<i class=\"fa fa-step-forward\"></i>",
                'conflict': "<span class=\"encircled\">1</span>",
                'conflic2': "<span class=\"encircled\">2</span>",
                'conflic3': "<span class=\"encircled\">3</span>",
                'time_relation': "&Delta;",
                'timerange': "<i class=\"fa fa-calendar-o\"></i>",
            }.get(cn.slug, cn.editor_label)

            cn.order = {
                'conflict': 1,
                'conflic2': 2,
                'conflic3': 3,
                'bethere': 4,
                'timerange': 5,
                'time_relation': 6,
                'wg_adjacent': 7,
            }.get(cn.slug, cn.order)

            cn.save()

    def noop(apps, schema_editor):
        pass

    operations = [
        migrations.AlterField(
            model_name='constraintname',
            name='editor_label',
            field=models.CharField(blank=True, help_text='Very short label for producing warnings inline in the sessions in the schedule editor.', max_length=64),
        ),
        migrations.RunPython(update_editor_labels, noop, elidable=True),
    ]
