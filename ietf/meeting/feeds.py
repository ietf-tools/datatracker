# Copyright The IETF Trust 2007-2024, All Rights Reserved
# -*- coding: utf-8 -*-


import os

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.conf import settings
from django.utils.html import escape

from ietf.doc.models import Document

class LatestMeetingMaterialFeed(Feed):
    feed_type = Atom1Feed
    link = "/meeting/"
    language = "en"
    base_url = "https://www.ietf.org/proceedings/"

    def items(self):
        objs = []
        # FIXME: why aren't other materials types in here?
        for doc in Document.objects.filter(type__in=("agenda", "minutes", "slides")).order_by('-time')[:60]:
            obj = dict(
                title=doc.type_id,
                group_acronym=doc.name.split("-")[2],
                date=doc.time,
                # FIXME: why isn't this using get_versionless_href or get_href?
                link=self.base_url + os.path.join(doc.get_file_path(), doc.uploaded_filename)[len(settings.AGENDA_PATH):],
                author=""
                )
            objs.append(obj)

        return objs

    def title(self, obj):
        return "Meeting Materials Activity"

    def item_title(self, item):
        return "%s: %s" % (item["group_acronym"], escape(item["title"]))

    def item_description(self, item):
        return ""

    def item_link(self, item):
        return item['link']

    def item_updateddate(self, item):
        return item['date']

    def item_author_name(self, item):
        return item['author']

    def item_author_email(self, item):
        return None
