# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from ietf.message.models import Message

class NOMCOMAnnouncementsMap(Sitemap):
    changefreq = "never"
    def items(self):
        return Message.objects.filter(related_groups__acronym__startswith="nomcom").exclude(related_groups__acronym="nomcom").order_by('-time')
    def location(self, obj):
	return "/ann/nomcom/%d/" % obj.id
    def lastmod(self, obj):
        # could re-parse the time into a datetime object
	return obj.time
