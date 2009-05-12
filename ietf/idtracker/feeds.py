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
	    return IDInternal.objects.get(draft=int(rfc.group(1)), rfc_flag=1)
	else:
	    return IDInternal.objects.get(draft__filename=bits[0], rfc_flag=0)

    def title(self, obj):
	# filename is a function for RFCs and an attribute for I-Ds.
	# This works transparently for templates but is not transparent
	# for python.
	if obj.rfc_flag:
	    filename = obj.document().filename()
	else:
	    filename = obj.document().filename
	return "I-D Tracker comments for %s" % filename

    def link(self, obj):
	if obj is None:
	    raise FeedDoesNotExist
	return obj.get_absolute_url()

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
	return obj.public_comments().order_by("-date","-id")

    def item_pubdate(self, item):
	time = datetime.time(*[int(t) for t in item.time.split(":")])
	return datetime.datetime.combine(item.date, time)

    def item_author_name(self, item):
	return item.get_author()

class InLastCall(Feed):
    title = "Documents in Last Call"
    feed_type = Atom1Feed
    author_name = 'IESG Secretary'
    link = "/idtracker/status/last-call/"

    def items(self):
	ret = list(IDInternal.objects.filter(primary_flag=1).filter(cur_state__state='In Last Call'))
	ret.sort(key=lambda item: (item.document().lc_expiration_date or datetime.date.today()))
	return ret

    def item_pubdate(self, item):
        return item.document().lc_sent_date

