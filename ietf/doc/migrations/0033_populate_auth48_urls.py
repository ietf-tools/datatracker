# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import OuterRef, Subquery

from re import match


def forward(apps, schema_editor):
    """Add DocumentURLs for docs in the Auth48 state

    Checks the latest StateDocEvent; if it is in the auth48 state and the
    event desc has an AUTH48 link, creates an auth48 DocumentURL for that doc.
    """
    Document = apps.get_model('doc', 'Document')
    StateDocEvent = apps.get_model('doc', 'StateDocEvent')
    DocumentURL = apps.get_model('doc', 'DocumentURL')

    # Regex - extracts auth48 URL as first match group
    pattern = r'RFC Editor state changed to <a href="(.*)"><b>AUTH48.*</b></a>.*'

    # To avoid 100k queries, set up a subquery to find the latest StateDocEvent for each doc...
    latest_events = StateDocEvent.objects.filter(doc=OuterRef('pk')).order_by('-time', '-id')
    # ... then annotate the doc list with that and select only those in the auth48 state...
    auth48_docs = Document.objects.annotate(
        current_state_slug=Subquery(latest_events.values('state__slug')[:1])
    ).filter(current_state_slug='auth48')
    # ... and add an auth48 DocumentURL if one is found.
    for doc in auth48_docs:
        # Retrieve the full StateDocEvent. Results in a query per doc, but
        # only for the few few in the auth48 state.
        sde = StateDocEvent.objects.filter(doc=doc).order_by('-time', '-id').first()
        urlmatch = match(pattern, sde.desc)  # Auth48 URL is usually in the event desc
        if urlmatch is not None:
            DocumentURL.objects.create(doc=doc, tag_id='auth48', url=urlmatch[1])

    # Validate the migration using a different approach to find auth48 docs.
    # This is slower than above, but still avoids querying for every Document.
    auth48_events = StateDocEvent.objects.filter(state__slug='auth48')
    for a48_event in auth48_events:
        doc = a48_event.doc
        latest_sde = StateDocEvent.objects.filter(doc=doc).order_by('-time', '-id').first()
        if latest_sde.state and latest_sde.state.slug == 'auth48' and match(pattern, latest_sde.desc) is not None:
            # Currently in the auth48 state with a URL
            assert doc.documenturl_set.filter(tag_id='auth48').count() == 1
        else:
            # Either no longer in auth48 state or had no URL
            assert doc.documenturl_set.filter(tag_id='auth48').count() == 0


def reverse(apps, schema_editor):
    """Remove any auth48 DocumentURLs - these did not exist before"""
    DocumentURL = apps.get_model('doc', 'DocumentURL')
    DocumentURL.objects.filter(tag_id='auth48').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('doc', '0032_auto_20200624_1332'),
        ('name', '0013_add_auth48_docurltagname'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
