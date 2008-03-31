# Copyright The IETF Trust 2007, 2008, All Rights Reserved

from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.iesg.models import TelechatMinutes
from ietf.idtracker.models import IDInternal
import datetime

class IESGMinutes(Feed):
    title = "IESG Telechat Minutes"
    link = "/iesg/telechat/"
    subtitle = "Minutes from IESG Telechats."
    feed_type = Atom1Feed
    author_name = 'IESG Secretary'

    def items(self):
	return TelechatMinutes.objects.order_by('-telechat_date')[:10]

    def item_link(self, item):
	return "/iesg/telechat/%d/" % (item.id)

    # The approval date isn't stored, so let's just say they're
    # published on the date of the telechat.
    def item_pubdate(self, item):
	# (slightly better would be 0900 Eastern on this date)
	return item.telechat_date

class IESGAgenda(Feed):
    title = "IESG Telechat Agenda"
    link = "http://www.ietf.org/IESG/agenda.html"
    subtitle = "Documents on upcoming IESG Telechat Agendas."
    feed_type = Atom1Feed

    def items(self):
	return IDInternal.objects.filter(agenda=1).order_by('telechat_date')

    def item_categories(self, item):
	return [ str(item.telechat_date) ]

    def item_pubdate(self, item):
	f = item.comments().filter(comment_text__startswith='Placed on agenda for telechat')
	try:
	   comment = f[0]
	   date = comment.datetime()
	except IndexError:
	   date = datetime.datetime.now() #XXX
	return date

    def item_author_name(self, item):
	return str( item.job_owner )
    def item_author_email(self, item):
	return item.job_owner.person.email()[1]
