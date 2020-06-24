# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.urls import reverse as urlreverse
from django.utils.html import strip_tags
from django.template.defaultfilters import truncatewords

from ietf.group.models import Group, GroupEvent
from ietf.doc.models import DocEvent

class GroupChangesFeed(Feed):
    feed_type = Atom1Feed
    description_template = "group/feed_item_description.html"

    def get_object(self, request, acronym):
        return Group.objects.get(acronym=acronym)

    def title(self, obj):
        return "Changes for %s %s" % (obj.acronym, obj.type)

    def link(self, obj):
        if not obj:
            raise FeedDoesNotExist
        return obj.about_url()

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
            return urlreverse("ietf.doc.views_doc.document_main", kwargs={'name': obj.doc.name })
        elif isinstance(obj, GroupEvent):
            return obj.group.about_url()

    def item_pubdate(self, obj):
        return obj.time

    def item_title(self, obj):
        title = "%s - %s" % (truncatewords(strip_tags(obj.desc), 10), obj.by)
        if isinstance(obj, DocEvent):
            title = "Chartering: %s" % title

        return title
