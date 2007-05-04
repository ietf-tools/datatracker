from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.idtracker.models import InternetDraft, DocumentComment
import datetime

class DocumentComments(Feed):
    feed_type = Atom1Feed
    def get_object(self, bits):
	if len(bits) != 1:
	    raise ObjectDoesNotExist
	return InternetDraft.objects.get(filename=bits[0])

    def title(self, obj):
	return "I-D Tracker comments for %s" % obj.filename

    def link(self, obj):
	return "/idtracker/%s" % obj.filename
	# obj.get_absolute_url() ?

    def description(self, obj):
	self.title(obj)

    def items(self, obj):
	return DocumentComment.objects.filter(document=obj.id_document_tag).order_by("-date")[:15]

    def item_pubdate(self, item):
	time = datetime.time(*[int(t) for t in item.time.split(":")])
	return datetime.datetime.combine(item.date, time)

    def item_author_name(self, item):
	return item.get_author()
