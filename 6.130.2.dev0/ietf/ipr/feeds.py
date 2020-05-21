# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text

from ietf.ipr.models import IprDisclosureBase

class LatestIprDisclosuresFeed(Feed):
    feed_type = Atom1Feed
    title = "IPR Disclosures to the IETF"
    link = reverse_lazy('ietf.ipr.views.showlist')
    description = "Updates on new IPR Disclosures made to the IETF."
    language = "en"
    feed_url = "/feed/ipr/"

    def items(self):
        return IprDisclosureBase.objects.filter(state__in=('posted','removed')).order_by('-time')[:30]

    def item_title(self, item):
        return mark_safe(item.title)

    def item_description(self, item):
        return force_text(item.title)
        
    def item_pubdate(self, item):
        return item.time

    def item_author_name(self, item):
        if item.by:
            return item.by.name
        else:
            return None

    def item_author_email(self, item):
        if item.by:
            return item.by.email_address()
        else:
            return None
