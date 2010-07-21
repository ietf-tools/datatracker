# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.sitemaps import Sitemap
from ietf.announcements.models import Announcement

class NOMCOMAnnouncementsMap(Sitemap):
    changefreq = "never"
    def items(self):
        return Announcement.objects.all().filter(nomcom=True)
    def location(self, obj):
	return "/ann/nomcom/%d/" % obj.announcement_id
    def lastmod(self, obj):
        # could re-parse the time into a datetime object
	return obj.announced_date
