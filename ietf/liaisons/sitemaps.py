# Copyright The IETF Trust 2007, All Rights Reserved
#
from django.contrib.sitemaps import Sitemap
from ietf.liaisons.models import LiaisonDetail

class LiaisonMap(Sitemap):
    changefreq = "never"
    def items(self):
        return LiaisonDetail.objects.all()
    def location(self, obj):
	return "/liaison/%d/" % obj.detail_id
    def lastmod(self, obj):
	return obj.last_modified_date
