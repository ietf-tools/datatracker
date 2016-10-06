# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

import debug                            # pyflakes:ignore

verbose = False
def note(s):
    if verbose:
        print(s)


def clean_up_duplicate_upload_docevents(apps, schema_editor):
    DocEvent = apps.get_model('doc', 'DocEvent')
    DocHistory = apps.get_model('doc', 'DocHistory')

    def get_dochistory(e):
        return DocHistory.objects.filter(time__lte=e.time,doc__name=e.doc.name).order_by('-time', '-pk').first()

    def rev(e):
        if hasattr(e, 'newrevisiondocevent'):
            return e.newrevisiondocevent.rev
        else:
            h = get_dochistory(e)
            if h:
                return h.rev
            else:
                return "  "

    events = DocEvent.objects.filter(time__gt='2016-09-10', doc__type='draft', desc='Uploaded new revision').order_by('id')
    docs = set()
    for e in events:
        docs.add(e.doc)
    for doc in docs:
        note("\n%s" % doc.name)
        docevents = list(events.filter(doc=doc))
        prev = docevents[0]
        for i, event in enumerate(docevents):
            if rev(event) != rev(prev):
                note("")
            if event.time < prev.time:
                print( "    *** Timestamp discrepancy:")
            note((u"    %6d  %s  %-20s  %s  %s" % (event.id, event.time, event.by.name[:24], rev(event), event.desc[:64].replace('\n',''), )).encode('utf-8'))
            if event.by.name == '(System)':
                for j in range(i+1, len(docevents)):
                    next = docevents[j]
                    if rev(next) == rev(event):
                        note((u"    Deleting event %6d  %s  %-20s  %s" % (event.id, event.time, event.by.name[:24], rev(event), )).encode('utf-8'))
                        event.delete()
                        break
            prev = event
    return False

def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    
    dependencies = [
        ('submit', '0015_fix_bad_submission_docevents'),
    ]

    operations = [
        migrations.RunPython(clean_up_duplicate_upload_docevents, noop)
    ]
