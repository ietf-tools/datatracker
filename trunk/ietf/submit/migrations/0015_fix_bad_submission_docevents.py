# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

import debug                            # pyflakes:ignore

verbose = False
def note(s):
    if verbose:
        print(s)

class Migration(migrations.Migration):
    
    def clean_up_bad_docevent_dates(apps, schema_editor):
        DocEvent = apps.get_model('doc', 'DocEvent')
        events = DocEvent.objects.filter(time__gt='2016-09-10', doc__type='draft').order_by('id')
        docs = set()
        for e in events:
            docs.add(e.doc)
        for doc in docs:
            docevents = events.filter(doc=doc)
            prev = docevents.first()
            doc_shown = False
            prev_shown = False
            new_rev_msgs = []
            for e in docevents:
                if e.type == 'new_revision':
                    new_rev_msgs.append(e.desc)
                if e.time < prev.time:
                    if not doc_shown:
                        note("\n%s:" % doc.name)
                        doc_shown = True
                    if not prev_shown:
                        note("\n   ---- %s: %-14s %s" % (prev.time, prev.type, prev.desc))
                        prev_shown = True
                    note((u"   bad: %s: %-14s %s" % (e.time, e.type, e.desc)).encode('utf8'))
                    if e.type == 'new_revision' and e.desc in new_rev_msgs:
                        note(" * deleting duplicate new_revision event")
                        e.newrevisiondocevent.delete()
                    else:
                        note((u" * fixing time of event %s %s" % (e.time, e.desc)).encode('utf8'))
                        e.time = prev.time
                        e.save()
                else:
                    prev = e
                    prev_shown = False

    def noop(apps, schema_editor):
        pass

    dependencies = [
        ('submit', '0014_auto_20160627_1945'),
    ]

    operations = [
        migrations.RunPython(clean_up_bad_docevent_dates, noop)
    ]
