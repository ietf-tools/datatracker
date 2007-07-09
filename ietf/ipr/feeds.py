# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.ipr.models import IprDetail

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
        return item.submitted_date
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
