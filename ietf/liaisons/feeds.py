# Copyright The IETF Trust 2007, All Rights Reserved

import re

from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.template.loader import render_to_string
from django.db.models import Q
from django.core.urlresolvers import reverse as urlreverse, reverse_lazy

from ietf.group.models import Group
from ietf.liaisons.models import LiaisonStatement

# A slightly funny feed class, the 'object' is really
# just a dict with some parameters that items() uses
# to construct a queryset.
class LiaisonStatementsFeed(Feed):
    feed_type = Atom1Feed
    link = reverse_lazy("ietf.liaisons.views.liaison_list")

    def get_object(self, request, kind, search=None):
        obj = {}

        if kind == 'recent':
            obj['title'] = 'Recent Liaison Statements'
            obj['limit'] = 15
            return obj

        if kind == 'from':
            if not search:
                raise FeedDoesNotExist

            try:
                group = Group.objects.get(acronym=search)
                obj['filter'] = { 'from_groups': group }
                obj['title'] = u'Liaison Statements from %s' % group.name
                return obj
            except Group.DoesNotExist:
                # turn all-nonword characters into one-character
                # wildcards to make it easier to construct a URL that
                # matches
                search_string = re.sub(r"[^a-zA-Z1-9]", ".", search)
                statement = LiaisonStatement.objects.filter(from_groups__name__iregex=search_string).first()
                if not statement:
                    raise FeedDoesNotExist

                name = statement.from_groups.first().name
                obj['filter'] = { 'from_name': name }
                obj['title'] = u'Liaison Statements from %s' % name
                return obj

        if kind == 'to':
            if not search:
                raise FeedDoesNotExist

            group = Group.objects.get(acronym=search)
            obj['filter'] = { 'to_groups': group }
            obj['title'] = u'Liaison Statements to %s' % group.name
            return obj

        if kind == 'subject':
            if not search:
                raise FeedDoesNotExist

            obj['q'] = [ Q(title__icontains=search) | Q(attachments__title__icontains=search) ]
            obj['title'] = 'Liaison Statements where subject matches %s' % search
            return obj

        raise FeedDoesNotExist

    def items(self, obj):
        qs = LiaisonStatement.objects.all().order_by("-id")
        if obj.has_key('q'):
            qs = qs.filter(*obj['q'])
        if obj.has_key('filter'):
            qs = qs.filter(**obj['filter'])
        if obj.has_key('limit'):
            qs = qs[:obj['limit']]

        qs = qs.prefetch_related("attachments")

	return qs

    def title(self, obj):
        return obj['title']

    def description(self, obj):
        return self.title(obj)

    def item_title(self, item):
        return render_to_string("liaisons/liaison_title.html", { 'liaison': item }).strip()

    def item_description(self, item):
        return render_to_string("liaisons/feed_item_description.html", {
            'liaison': item,
            "attachments": item.attachments.all(),
        })

    def item_link(self, item):
        return urlreverse("ietf.liaisons.views.liaison_detail", kwargs={ "object_id": item.pk })

    def item_pubdate(self, item):
        # this method needs to return a datetime instance, even
        # though the database has only date, not time
        return item.submitted

    def item_author_name(self, item):
        return item.from_groups.first().name
