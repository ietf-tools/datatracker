# Copyright The IETF Trust 2011, All Rights Reserved

import datetime, re, os

from django.conf import settings
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.core.urlresolvers import reverse as urlreverse
from django.utils.html import strip_tags
from django.utils.text import truncate_words

from ietf.utils.history import find_history_active_at
from ietf.group.models import Group, GroupEvent
from ietf.doc.models import DocEvent

class GroupChanges(Feed):
    feed_type = Atom1Feed
    description_template = "feeds/group_description.html"
    def get_object(self, bits):
	if len(bits) != 1:
	    raise Group.DoesNotExist
        return Group.objects.get(acronym=bits[0])

    def title(self, obj):
        return u"Changes for %s %s" % (obj.acronym, obj.type)

    def link(self, obj):
	if not obj:
	    raise FeedDoesNotExist
	return urlreverse('wg_charter', kwargs={'acronym': obj.acronym})

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
        events = list(obj.groupevent_set.all().select_related("group"))
        if obj.charter:
            events += list(obj.charter.docevent_set.all())

        events.sort(key=lambda e: (e.time, e.id), reverse=True)

        return events

    def item_link(self, obj):
        if isinstance(obj, DocEvent):
            return urlreverse("doc_view", kwargs={'name': obj.doc_id })
        elif isinstance(obj, GroupEvent):
            return urlreverse('wg_charter', kwargs={'acronym': obj.group.acronym })

    def item_pubdate(self, obj):
	return obj.time

    def item_title(self, obj):
        title = u"%s - %s" % (truncate_words(strip_tags(obj.desc), 10), obj.by)
        if isinstance(obj, DocEvent):
            title = u"Chartering: %s" % title

        return title
