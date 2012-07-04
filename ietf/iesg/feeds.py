# Copyright The IETF Trust 2007, 2008, All Rights Reserved

from django.conf import settings
from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.doc.models import Document
import datetime

class IESGAgenda(Feed):
    title = "Documents on Future IESG Telechat Agendas"
    link = "http://datatracker.ietf.org/iesg/agenda/"
    feed_type = Atom1Feed

    def items(self):
        from ietf.doc.models import TelechatDocEvent
        drafts = Document.objects.filter(docevent__telechatdocevent__telechat_date__gte=datetime.date.min).distinct()
        for d in drafts:
            d.latest_telechat_event = d.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        drafts = [d for d in drafts if d.latest_telechat_event.telechat_date]
        drafts.sort(key=lambda d: d.latest_telechat_event.telechat_date)
        return drafts


    def item_categories(self, item):
	return [ str(item.telechat_date) ]

    def item_pubdate(self, item):
        return item.latest_telechat_event.time
        
    def item_author_name(self, item):
	return str( item.ad ) if item.ad else "None"

    def item_author_email(self, item):
        return str( item.ad.role_email("ad") ) if item.ad else ""
