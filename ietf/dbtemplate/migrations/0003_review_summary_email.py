# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    Group = apps.get_model('group','Group')

    DBTemplate.objects.create(
        path='/group/defaults/email/open_assignments.txt',
        title='Default template for review team open assignment summary email',
        type_id='django',
        group=None,
        content="""{% autoescape off %}Subject: Open review assignments in {{group.acronym}}

The following reviewers have assignments:{% for r in review_requests %}{% ifchanged r.section %}

{{r.section}}

{% if r.section == 'Early review requests:' %}Reviewer               Due        Draft{% else %}Reviewer               LC end     Draft{% endif %}{% endifchanged %}
{{ r.reviewer.person.plain_name|ljust:"22" }} {% if r.section == 'Early review requests:' %}{{ r.deadline|date:"Y-m-d" }}{% else %}{{ r.lastcall_ends|default:"None      " }}{% endif %} {{ r.doc_id }}-{% if r.requested_rev %}{{ r.requested_rev }}{% else %}{{ r.doc.rev }}{% endif %} {{ r.earlier_review_mark }}{% endfor %}

* Other revision previously reviewed
** This revision already reviewed

{% if rotation_list %}Next in the reviewer rotation:

{% for p in rotation_list %}  {{ p }}
{% endfor %}{% endif %}{% endautoescape %}
"""
    )

    DBTemplate.objects.create(
        path='/group/genart/email/open_assignments.txt',
        title='Genart open assignment summary',
        type_id='django',
        group=Group.objects.get(acronym='genart'),
        content="""{% autoescape off %}Subject: Review Assignments

Hi all,

The following reviewers have assignments:{% for r in review_requests %}{% ifchanged r.section %}

{{r.section}}

{% if r.section == 'Early review requests:' %}Reviewer               Due        Draft{% else %}Reviewer               LC end     Draft{% endif %}{% endifchanged %}
{{ r.reviewer.person.plain_name|ljust:"22" }} {% if r.section == 'Early review requests:' %}{{ r.deadline|date:"Y-m-d" }}{% else %}{{ r.lastcall_ends|default:"None      " }}{% endif %} {{ r.doc_id }}-{% if r.requested_rev %}{{ r.requested_rev }}{% else %}{{ r.doc.rev }}{% endif %} {{ r.earlier_review_mark }}{% endfor %}

* Other revision previously reviewed
** This revision already reviewed

{% if rotation_list %}Next in the reviewer rotation:

{% for p in rotation_list %}  {{ p }}
{% endfor %}{% endif %}
The LC and Telechat review templates are included below:
-------------------------------------------------------

-- Begin LC Template --
I am the assigned Gen-ART reviewer for this draft. The General Area
Review Team (Gen-ART) reviews all IETF documents being processed
by the IESG for the IETF Chair.  Please treat these comments just
like any other last call comments.

For more information, please see the FAQ at

<https://trac.ietf.org/trac/gen/wiki/GenArtfaq>.

Document:
Reviewer:
Review Date:
IETF LC End Date:
IESG Telechat date: (if known)

Summary:

Major issues:

Minor issues:

Nits/editorial comments: 

-- End LC Template --

-- Begin Telechat Template --
I am the assigned Gen-ART reviewer for this draft. The General Area
Review Team (Gen-ART) reviews all IETF documents being processed
by the IESG for the IETF Chair. Please wait for direction from your
document shepherd or AD before posting a new version of the draft.

For more information, please see the FAQ at

<https://trac.ietf.org/trac/gen/wiki/GenArtfaq>.

Document:
Reviewer:
Review Date:
IETF LC End Date:
IESG Telechat date: (if known)

Summary:

Major issues:

Minor issues:

Nits/editorial comments:

-- End Telechat Template --
{% endautoescape %}
"""
    )

    DBTemplate.objects.create(
        path='/group/secdir/email/open_assignments.txt',
        title='Secdir open assignment summary',
        type_id='django',
        group=Group.objects.get(acronym='secdir'),
        content="""{% autoescape off %}Subject: Assignments

Review instructions and related resources are at:
http://tools.ietf.org/area/sec/trac/wiki/SecDirReview{% for r in review_requests %}{% ifchanged r.section %}

{{r.section}}

{% if r.section == 'Early review requests:' %}Reviewer               Due        Draft{% else %}Reviewer               LC end     Draft{% endif %}{% endifchanged %}
{{ r.reviewer.person.plain_name|ljust:"22" }}{{ r.earlier_review|yesno:'R, , ' }}{% if r.section == 'Early review requests:' %}{{ r.deadline|date:"Y-m-d" }}{% else %}{{ r.lastcall_ends|default:"None      " }}{% endif %} {{ r.doc_id }}-{% if r.requested_rev %}{{ r.requested_rev }}{% else %}{{ r.doc.rev }}{% endif %}{% endfor %}

{% if rotation_list %}Next in the reviewer rotation:

{% for p in rotation_list %}  {{ p }}
{% endfor %}{% endif %}{% endautoescape %}
"""
    )

def reverse(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    DBTemplate.objects.filter(path__in=['/group/defaults/email/open_assignments.txt',
                                        '/group/genart/email/open_assignments.txt',
                                        '/group/secdir/email/open_assignments.txt',]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('dbtemplate', '0002_auto_20141222_1749'),
        ('group', '0009_auto_20150930_0758'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
