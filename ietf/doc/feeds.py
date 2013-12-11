# Copyright The IETF Trust 2007, All Rights Reserved

import datetime, re

from django.conf import settings
from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.core.urlresolvers import reverse as urlreverse
from django.template.defaultfilters import truncatewords, truncatewords_html, date as datefilter, linebreaks
from django.utils.html import strip_tags

from ietf.doc.models import *
from ietf.doc.utils import augment_events_with_revision
from ietf.doc.templatetags.ietf_filters import format_textarea

class DocumentChanges(Feed):
    feed_type = Atom1Feed

    def get_object(self, bits):
	if len(bits) != 1:
	    raise Document.DoesNotExist

        return Document.objects.get(docalias__name=bits[0])

    def title(self, obj):
        return "Changes for %s" % obj.display_name()

    def link(self, obj):
	if obj is None:
	    raise FeedDoesNotExist
        if not hasattr(self, "cached_link"):
            self.cached_link = urlreverse("doc_history", kwargs=dict(name=obj.canonical_name()))
	return self.cached_link

    def subtitle(self, obj):
        return "History of change entries for %s." % obj.display_name()

    def items(self, obj):
        events = obj.docevent_set.all().order_by("-time","-id")
        augment_events_with_revision(obj, events)
	return events

    def item_title(self, item):
        return u"[%s] %s [rev. %s]" % (item.by, truncatewords(strip_tags(item.desc), 15), item.rev)

    def item_description(self, item):
        return truncatewords_html(format_textarea(item.desc), 20)

    def item_pubdate(self, item):
	return item.time

    def item_author_name(self, item):
	return unicode(item.by)

    def item_link(self, item):
        return self.cached_link + "#history-%s" % item.pk

class InLastCall(Feed):
    title = "Documents in Last Call"
    subtitle = "Announcements for documents in last call."
    feed_type = Atom1Feed
    author_name = 'IESG Secretary'
    link = "/doc/iesg/last-call/"

    def items(self):
        docs = list(Document.objects.filter(type="draft", states=State.objects.get(type="draft-iesg", slug="lc")))
        for d in docs:
            d.lc_event = d.latest_event(LastCallDocEvent, type="sent_last_call")

        docs = [d for d in docs if d.lc_event]
	docs.sort(key=lambda d: d.lc_event.expires)

	return docs

    def item_title(self, item):
        return u"%s (%s - %s)" % (item.name,
                                datefilter(item.lc_event.time, "F j"),
                                datefilter(item.lc_event.expires, "F j, Y"))

    def item_description(self, item):
        return linebreaks(item.lc_event.desc)

    def item_pubdate(self, item):
        return item.lc_event.time

