# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import uuid

import debug  # pyflakes:ignore

from django.contrib.syndication.views import Feed
from django.http import HttpResponse
from django.utils import timezone
from django.utils.feedgenerator import Atom1Feed

from ietf.community.utils import states_of_significant_change
from ietf.community.views import lookup_community_list, MultiplePersonError
from ietf.doc.models import DocEvent

class Atom1WithNamespacesFeed(Atom1Feed):
    def root_attributes(self):
        attrs = super(Atom1WithNamespacesFeed, self).root_attributes()
        attrs["xmlns:ietf"] = "http://ietf.org/atom/datatracker/community"
        return attrs

    def add_item_elements(self, handler, item):
        super(Atom1WithNamespacesFeed, self).add_item_elements(handler, item)

        for element_name in [
            "type",
            "stream",
            "group",
            "shepherd",
            "ad",
            "abstract",
            "version",
        ]:
            ietf_item_name = "ietf_%s" % element_name
            ietf_element_name = "ietf:%s" % element_name
            if ietf_item_name in item and item[ietf_item_name] is not None:
                handler.addQuickElement(ietf_element_name, item[ietf_item_name])

        if "ietf_state" in item and item["ietf_state"] is not None:
            for state in item["ietf_state"]:
                handler.addQuickElement("ietf:state", state["value"], {"type": state["type"]})

        if "ietf_tag" in item and item["ietf_tag"] is not None:
            for tag in item["ietf_tag"]:
                handler.addQuickElement("ietf:tag", tag)

class CommunityFeed(Feed):
    feed_type = Atom1WithNamespacesFeed

    def __call__(self, request, *args, **kwargs):
        try:
            return super(CommunityFeed, self).__call__(request, *args, **kwargs)
        except MultiplePersonError as err:
            return HttpResponse(str(err), status=300)

    def get_object(self, request, *args, **kwargs):
        email_or_name = kwargs["email_or_name"]
        acronym = kwargs["acronym"]
        clist = lookup_community_list(request, email_or_name, acronym)
        self.significant = request.GET.get('significant', '') == '1'
        self.host = request.get_host()
        self.feed_url = 'https://%s%s' % (self.host, request.get_full_path())
        return clist

    def title(self, obj):
        return '%s RSS Feed' % obj.long_name()

    def subtitle(self):
        if self.significant:
            subtitle = 'Significant document changes'
        else:
            subtitle = 'Document changes'
        return subtitle

    def link(self):
        return self.host

    def feed_url(self, obj):
        return self.feed_url

    def feed_guid(self, obj):
        feed_id = uuid.uuid5(uuid.NAMESPACE_URL, str(self.feed_url))
        return feed_id.urn

    def items(self, obj):
        from ietf.community.utils import docs_tracked_by_community_list
        documents = docs_tracked_by_community_list(obj).values_list('pk', flat=True)
        since = timezone.now() - datetime.timedelta(days=21)
        events = DocEvent.objects.filter(
            doc__id__in=documents,
            time__gte=since,
        ).distinct().order_by('-time', '-id').select_related("doc")
        if self.significant:
            events = events.filter(type="changed_state", statedocevent__state__in=list(states_of_significant_change()))
        return events[:50]

    def item_title(self, item):
        title = item.doc.title
        if item.type == 'sent_last_call':
            title = "Last Call Issued: %s" % title
        return title

    def item_description(self, item):
        return item.desc	# {{ entry.desc|linebreaksbr|force_escape }}

    def item_link(self, item):
        return item.doc.get_absolute_url()

    def item_guid(self, item):
        return "urn:uid:%s" % item.id

    def item_pubdate(self, item):
        return item.time

    def item_updateddate(self, item):
        return item.time

    def item_author_name(self, item):
        return str(item.by)

    def item_extra_kwargs(self, item):
        extra = super(CommunityFeed, self).item_extra_kwargs(item)
        extra.update({"ietf_type": item.type})
        if item.doc.stream.slug:
            extra.update({"ietf_stream": item.doc.stream.slug})
        extra.update({"ietf_group": item.doc.group.acronym})
        if item.doc.shepherd:
            extra.update({"ietf_shepherd": item.doc.shepherd.person.name})
        if item.doc.ad:
            extra.update({"ietf_ad": item.doc.ad.name})
        if item.doc.states:
            extra.update({"ietf_state": [{"type": str(state.type), "value": state.slug} for state in item.doc.states.all()]})
        if item.doc.tags:
            extra.update({"ietf_tag": [tag.slug for tag in item.doc.tags.all()]})
        if item.type == "new_revision":
            if item.doc.abstract:
                extra.update({"ietf_abstract": item.doc.abstract})
            if item.doc.rev:
                extra.update({"ietf_version": item.doc.rev})
        return extra
