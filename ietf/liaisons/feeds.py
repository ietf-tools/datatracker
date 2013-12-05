# Copyright The IETF Trust 2007, All Rights Reserved

import re, datetime

from django.conf import settings
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.db.models import Q
from django.core.urlresolvers import reverse as urlreverse

from ietf.group.models import Group
from ietf.liaisons.models import LiaisonStatement

# A slightly funny feed class, the 'object' is really
# just a dict with some parameters that items() uses
# to construct a queryset.
class Liaisons(Feed):
    feed_type = Atom1Feed

    def get_object(self, bits):
	obj = {}
	if bits[0] == 'recent':
	    if len(bits) != 1:
		raise FeedDoesNotExist
	    obj['title'] = 'Recent Liaison Statements'
	    obj['limit'] = 15
	    return obj

        if bits[0] == 'from':
	    if len(bits) != 2:
		raise FeedDoesNotExist
            try:
                group = Group.objects.get(acronym=bits[1])
                obj['filter'] = { 'from_group': group }
                obj['title'] = u'Liaison Statements from %s' % group.name
                return obj
            except Group.DoesNotExist:
                # turn all-nonword characters into one-character
                # wildcards to make it easier to construct a URL that
                # matches
                search_string = re.sub(r"[^a-zA-Z1-9]", ".", bits[1])
                statements = LiaisonStatement.objects.filter(from_name__iregex=search_string)
                if statements:
                    name = statements[0].from_name
                    obj['filter'] = { 'from_name': name }
                    obj['title'] = u'Liaison Statements from %s' % name
                    return obj
                else:
                    raise FeedDoesNotExist

        if bits[0] == 'to':
	    if len(bits) != 2:
		raise FeedDoesNotExist
            obj['filter'] = dict(to_name__icontains=bits[1])
            obj['title'] = 'Liaison Statements where to matches %s' % bits[1]
            return obj

	if bits[0] == 'subject':
	    if len(bits) != 2:
		raise FeedDoesNotExist

            obj['q'] = [ Q(title__icontains=bits[1]) | Q(attachments__title__icontains=bits[1]) ]
            obj['title'] = 'Liaison Statements where subject matches %s' % bits[1]
	    return obj
	raise FeedDoesNotExist

    def get_feed(self, url=None):
        if url:
            return Feed.get_feed(self, url=url)
        else:
            raise FeedDoesNotExist

    def title(self, obj):
	return obj['title']

    def link(self, obj):
	# no real equivalent for any objects
	return '/liaison/'

    def item_link(self, obj):
	# no real equivalent for any objects
        return urlreverse("liaison_detail", kwargs={ "object_id": obj.pk })

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
	# Start with the common queryset
        qs = LiaisonStatement.objects.all().order_by("-submitted")
	if obj.has_key('q'):
	    qs = qs.filter(*obj['q'])
	if obj.has_key('filter'):
	    qs = qs.filter(**obj['filter'])
	if obj.has_key('limit'):
	    qs = qs[:obj['limit']]
	return qs

    def item_pubdate(self, item):
        # this method needs to return a datetime instance, even
        # though the database has only date, not time 
        return item.submitted
 
    def item_author_name(self, item):
        return item.from_name
