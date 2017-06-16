# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    Group = apps.get_model('group','Group')

    DBTemplate.objects.create(
        path='/group/genart/review/content_templates/lc.txt',
        title='Template for genart last call reviews',
        type_id='django',
        group=Group.objects.get(acronym='genart'),
        content="""I am the assigned Gen-ART reviewer for this draft. The General Area
Review Team (Gen-ART) reviews all IETF documents being processed
by the IESG for the IETF Chair.  Please treat these comments just
like any other last call comments.

For more information, please see the FAQ at

<https://trac.ietf.org/trac/gen/wiki/GenArtfaq>.

Document: {{ review_req.doc.name }}-??
Reviewer: {{ review_req.reviewer.person.plain_name }}
Review Date: {{ today }}
IETF LC End Date: {% if review_req.doc.most_recent_ietflc %}{{ review_req.doc.most_recent_ietflc.expires|date:"Y-m-d" }}{% else %}None{% endif %}
IESG Telechat date: {{ review_req.doc.telechat_date|default:'Not scheduled for a telechat }}

Summary:

Major issues:

Minor issues:

Nits/editorial comments: 
"""
    )
    DBTemplate.objects.create(
        path='/group/genart/review/content_templates/telechat.txt',
        title='Template for genart telechat reviews',
        type_id='django',
        group=Group.objects.get(acronym='genart'),
        content="""I am the assigned Gen-ART reviewer for this draft. The General Area
Review Team (Gen-ART) reviews all IETF documents being processed
by the IESG for the IETF Chair. Please wait for direction from your
document shepherd or AD before posting a new version of the draft.

For more information, please see the FAQ at

<https://trac.ietf.org/trac/gen/wiki/GenArtfaq>.

Document: {{ review_req.doc.name }}-??
Reviewer: {{ review_req.reviewer.person.plain_name }}
Review Date: {{ today }}
IETF LC End Date: {% if review_req.doc.most_recent_ietflc %}{{ review_req.doc.most_recent_ietflc.expires|date:"Y-m-d" }}{% else %}None{% endif %}
IESG Telechat date: {{ review_req.doc.telechat_date|default:'Not scheduled for a telechat' }}

Summary:

Major issues:

Minor issues:

Nits/editorial comments: 
"""
    )

def reverse(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    DBTemplate.objects.filter(path__in=['/group/genart/review/content_templates/lc.txt','/group/genart/review/content_templates/telechat.txt']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dbtemplate', '0003_review_summary_email'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
