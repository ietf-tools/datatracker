# Copyright The IETF Trust 2020, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('name', '0011_constraintname_editor_label'),
    ]

    def update_editor_labels(apps, schema_editor):
        ConstraintName = apps.get_model('name', 'ConstraintName')
        for cn in ConstraintName.objects.all():
            cn.editor_label = {
                'bethere': "(person){count}",
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
        migrations.RunPython(update_editor_labels, noop, elidable=True),
    ]
