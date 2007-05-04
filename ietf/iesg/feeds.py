from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.iesg.models import TelechatMinutes

class IESGMinutes(Feed):
    title = "IESG Telechat Minutes"
    link = "/iesg/telechat/"
    subtitle = "Minutes from IESG Telechats."
    feed_type = Atom1Feed

    def items(self):
	return TelechatMinutes.objects.order_by('-telechat_date')[:10]

    def item_link(self, item):
	return "/iesg/telechat/detail/%d/" % (item.id)

    # The approval date isn't stored, so let's just say they're
    # published on the date of the telechat.
    def item_pubdate(self, item):
	# (slightly better would be 0900 Eastern on this date)
	return item.telechat_date
