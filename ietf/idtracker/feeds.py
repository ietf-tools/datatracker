# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from ietf.idtracker.models import IDInternal
import datetime
import re

class DocumentComments(Feed):
    feed_type = Atom1Feed
    def get_object(self, bits):
	if len(bits) != 1:
	    raise IDInternal.DoesNotExist
	rfc = re.match('rfc(\d+)', bits[0])
	if rfc:
	    return IDInternal.objects.get(draft_id=int(rfc.group(1)), rfc_flag=1)
	else:
	    return IDInternal.objects.get(draft__filename=bits[0], rfc_flag=0)

    def title(self, obj):
	return "I-D Tracker comments for %s" % obj.document().filename

    def link(self, obj):
	if obj is None:
	    raise FeedDoesNotExist
	return obj.get_absolute_url()

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
	return obj.public_comments().order_by("-date")[:15]

    def item_pubdate(self, item):
	time = datetime.time(*[int(t) for t in item.time.split(":")])
	return datetime.datetime.combine(item.date, time)

    def item_author_name(self, item):
	return item.get_author()
