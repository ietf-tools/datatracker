# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate', 'DBTemplate')

    DBTemplate.objects.create(path='/group/defaults/email/review_assigned.txt', type_id='django',
                              content="""{{ assigner.ascii }} has assigned you as a reviewer for this document.

{% if prev_team_reviews %}This team has completed other reviews of this document:{% endif %}{% for assignment in prev_team_reviews %}
- {{ assignment.completed_on }} {{ assignment.reviewer.person.ascii }} -{% if assignment.reviewed_rev %}{{ assignment.reviewed_rev }}{% else %}{{ assignment.review_request.requested_rev }}{% endif %} {{ assignment.result.name }}  
{% endfor %}
""")


def reverse(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate', 'DBTemplate')

    DBTemplate.objects.get(path='/group/defaults/email/review_assigned.txt').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dbtemplate', '0005_adjust_assignment_email_summary_templates_2526'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
