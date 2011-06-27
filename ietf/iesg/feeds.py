# Copyright The IETF Trust 2007, 2008, All Rights Reserved

from django.conf import settings
from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.idtracker.models import IDInternal
import datetime

class IESGAgenda(Feed):
    title = "Documents on Future IESG Telechat Agendas"
    link = "http://datatracker.ietf.org/iesg/agenda/"
    feed_type = Atom1Feed

    def items(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            from doc.models import TelechatDocEvent
            drafts = IDInternal.objects.filter(docevent__telechatdocevent__telechat_date__gte=datetime.date.min).distinct()
            for d in drafts:
                d.latest_telechat_event = d.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
            drafts = [d for d in drafts if d.latest_telechat_event.telechat_date]
            drafts.sort(key=lambda d: d.latest_telechat_event.telechat_date)
            return drafts

        return IDInternal.objects.filter(agenda=1).order_by('telechat_date')

    def item_categories(self, item):
	return [ str(item.telechat_date) ]

    def item_pubdate(self, item):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            return item.latest_telechat_event.time
        
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
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            return item.ad.email_address()
        
	return item.job_owner.person.email()[1]
