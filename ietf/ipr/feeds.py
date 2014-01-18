# Copyright The IETF Trust 2007, All Rights Reserved

import datetime

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.core.urlresolvers import reverse_lazy
from django.utils.safestring import mark_safe

from ietf.ipr.models import IprDetail

class LatestIprDisclosuresFeed(Feed):
    feed_type = Atom1Feed
    title = "IPR Disclosures to the IETF"
    link = reverse_lazy('ipr_showlist')
    description = "Updates on new IPR Disclosures made to the IETF."
    language = "en"
    feed_url = "/feed/ipr/"

    def items(self):
        return IprDetail.objects.filter(status__in=[1,3]).order_by('-submitted_date')[:30]

    def item_title(self, item):
        return mark_safe(item.title)

    def item_description(self, item):
        return unicode(item.title)
        
    def item_pubdate(self, item):
        # this method needs to return a datetime instance, even
        # though the database has only date, not time 
        return datetime.datetime.combine(item.submitted_date, datetime.time(0,0,0))

    def item_author_name(self, item):
        s = item.get_submitter()
        if s:
            return s.name
        return None

    def item_author_email(self, item):
	s = item.get_submitter()
	if s:
	    return s.email
        return None
