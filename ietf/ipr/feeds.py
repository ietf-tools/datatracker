# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.ipr.models import IprDetail
from datetime import datetime, time

class LatestIprDisclosures(Feed):
    feed_type = Atom1Feed
    title = "IPR Disclosures to the IETF"
    link = "/ipr/"
    description = "Updates on new IPR Disclosures made to the IETF."
    language = "en"
    feed_url = "/feed/ipr/"

    def items(self):
        return IprDetail.objects.filter(status__in=[1,3]).order_by('-submitted_date')[:15]
        
    def item_pubdate(self, item):
        # this method needs to return a datetime instance, even
        # though the database has only date, not time 
	return datetime.combine(item.submitted_date, time(0,0,0))
    def item_author_name(self, item):
	s = item.get_submitter()
        if s:
            if isinstance(s.name, unicode):
                # for django.VERSION[0] > 0
                return s.name
            else:
                # for django.VERSION[0] == 0
                return unicode(s.name, encoding='utf-8', errors='replace')
        return None
    def item_author_email(self, item):
	s = item.get_submitter()
	if s:
	    return s.email
        return None
