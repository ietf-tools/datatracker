# Copyright The IETF Trust 2007, All Rights Reserved
#
from django.contrib.sitemaps import Sitemap
from django.conf import settings
from ietf.idtracker.models import IDInternal, InternetDraft

class IDTrackerMap(Sitemap):
    changefreq = "always"
    def items(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            return IDInternal.objects.all()
        else:
            return IDInternal.objects.exclude(draft=999999)

class DraftMap(Sitemap):
    changefreq = "always"
    def items(self):
	return InternetDraft.objects.all()
    def location(self, obj):
	return "/drafts/%s/" % obj.filename
    def lastmod(self, obj):
	return obj.last_modified_date
