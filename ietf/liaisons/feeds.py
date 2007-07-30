# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from ietf.liaisons.models import LiaisonDetail, FromBodies
from ietf.idtracker.models import Acronym

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
	    obj['title'] = 'Liaison Statements from %s' % bits[1]
	    try:
		acronym = Acronym.objects.get(acronym=bits[1])
		obj['filter'] = {'from_id': acronym.acronym_id}
	    except Acronym.DoesNotExist:
		# would like to use from_body__body_name but relation
		# is broken due to database structure
		frmlist = [b['from_id'] for b in FromBodies.objects.filter(body_name=bits[1]).values('from_id')]
		if not frmlist:
		    raise FeedDoesNotExist
		obj['filter'] = {'from_id__in': frmlist}
	    return obj

    def title(self, obj):
	return obj['title']

    def link(self, obj):
	# no real equivalent for any objects
	return '/liaison/'

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
	# Start with the common queryset
	qs = LiaisonDetail.objects.all().order_by("-submitted_date")
	if obj.has_key('filter'):
	    qs = qs.filter(**obj['filter'])
	if obj.has_key('limit'):
	    qs = qs[:obj['limit']]
	return qs

    def item_pubdate(self, item):
	return item.submitted_date
