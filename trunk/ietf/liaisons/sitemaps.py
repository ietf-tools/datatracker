# Copyright The IETF Trust 2007, All Rights Reserved
#
from django.contrib.sitemaps import Sitemap

from ietf.liaisons.models import LiaisonStatement

class LiaisonMap(Sitemap):
    changefreq = "never"

    def items(self):
        return LiaisonStatement.objects.all()

    def location(self, obj):
        return "/liaison/%s/" % obj.pk

    def lastmod(self, obj):
        return obj.modified
