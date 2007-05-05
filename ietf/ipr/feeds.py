from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from ietf.ipr.models import IprDetail
import datetime

class LatestIprDisclosures(Feed):
    feed_type = Atom1Feed
    feed_url = "/feeds/ipr/"
    title = "IPR Disclosures to the IETF"
    link = "/ipr/"
    description = "Updates on new IPR Disclosures made to the IETF."
    language = "en"

    def items(self):
        return IprDetail.objects.order_by('-submitted_date')[:5]
        
    def item_link(self, item):
        return "/ipr/ipr-%s" % item.ipr_id
    def item_pubdate(self, item):
        return item.submitted_date
    def item_author_name(self, item):
        return item.get_submitter().name or None
    def item_author_email(self, item):
        return item.get_submitter().email or None
    
        