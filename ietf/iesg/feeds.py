# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from ietf.doc.models import Document, TelechatDocEvent
from ietf.utils.timezone import date_today


class IESGAgendaFeed(Feed):
    title = "Documents on Future IESG Telechat Agendas"
    link = "/iesg/agenda/"
    feed_type = Atom1Feed
    description_template = "iesg/feed_item_description.html"

    def items(self):
        docs = Document.objects.filter(docevent__telechatdocevent__telechat_date__gte=date_today(settings.TIME_ZONE)).distinct()
        for d in docs:
            d.latest_telechat_event = d.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        docs = [d for d in docs if d.latest_telechat_event.telechat_date]
        docs.sort(key=lambda d: d.latest_telechat_event.telechat_date, reverse=True)
        return docs

    def item_categories(self, doc):
        return [ str(doc.latest_telechat_event.time.date()) ]

    def item_updateddate(self, doc):
        return doc.latest_telechat_event.time
        
    def item_author_name(self, doc):
        return doc.ad.plain_name() if doc.ad else "None"

    def item_author_email(self, doc):
        if not doc.ad:
            return ""
        e = doc.ad.role_email("ad")
        if not e:
            return ""
        return e.address
