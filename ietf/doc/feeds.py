# Copyright The IETF Trust 2007, All Rights Reserved

import datetime

from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed
from django.core.urlresolvers import reverse as urlreverse
from django.template.defaultfilters import truncatewords, truncatewords_html, date as datefilter, linebreaks
from django.utils.html import strip_tags

from ietf.doc.models import Document, State, LastCallDocEvent, DocEvent
from ietf.doc.utils import augment_events_with_revision
from ietf.doc.templatetags.ietf_filters import format_textarea

class DocumentChangesFeed(Feed):
    feed_type = Atom1Feed

    def get_object(self, request, name):
        return Document.objects.get(docalias__name=name)

    def title(self, obj):
        return "Changes for %s" % obj.display_name()

    def link(self, obj):
	if obj is None:
	    raise FeedDoesNotExist
        return urlreverse("doc_history", kwargs=dict(name=obj.canonical_name()))

    def subtitle(self, obj):
        return "History of change entries for %s." % obj.display_name()

    def items(self, obj):
        events = obj.docevent_set.all().order_by("-time","-id")
        augment_events_with_revision(obj, events)
	return events

    def item_title(self, item):
        return u"[%s] %s [rev. %s]" % (item.by, truncatewords(strip_tags(item.desc), 15), item.rev)

    def item_description(self, item):
        return truncatewords_html(format_textarea(item.desc), 20)

    def item_pubdate(self, item):
	return item.time

    def item_author_name(self, item):
	return unicode(item.by)

    def item_link(self, item):
        return urlreverse("doc_history", kwargs=dict(name=item.doc.canonical_name())) + "#history-%s" % item.pk

class InLastCallFeed(Feed):
    title = "Documents in Last Call"
    subtitle = "Announcements for documents in last call."
    feed_type = Atom1Feed
    author_name = 'IESG Secretary'
    link = "/doc/iesg/last-call/"

    def items(self):
        docs = list(Document.objects.filter(type="draft", states=State.objects.get(type="draft-iesg", slug="lc")))
        for d in docs:
            d.lc_event = d.latest_event(LastCallDocEvent, type="sent_last_call")

        docs = [d for d in docs if d.lc_event]
	docs.sort(key=lambda d: d.lc_event.expires)

	return docs

    def item_title(self, item):
        return u"%s (%s - %s)" % (item.name,
                                datefilter(item.lc_event.time, "F j"),
                                datefilter(item.lc_event.expires, "F j, Y"))

    def item_description(self, item):
        return linebreaks(item.lc_event.desc)

    def item_pubdate(self, item):
        return item.lc_event.time

class Rss201WithNamespacesFeed(Rss201rev2Feed):
    def root_attributes(self):
        attrs = super(Rss201WithNamespacesFeed, self).root_attributes()
        attrs['xmlns:dcterms'] = 'http://purl.org/dc/terms/'
        attrs['xmlns:media'] = 'http://search.yahoo.com/mrss/'
        attrs['xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
        return attrs

    def add_item_elements(self, handler, item):
        super(Rss201WithNamespacesFeed, self).add_item_elements(handler, item)

        for element_name in ['abstract','accessRights', 'format', ]:
            dc_item_name = 'dcterms_%s' % element_name
            dc_element_name = 'dcterms:%s' % element_name
            if dc_item_name in item and item[dc_item_name] is not None:
                handler.addQuickElement(dc_element_name,item[dc_item_name])

        if 'doi' in item and item['doi'] is not None:
           handler.addQuickElement('dcterms:identifier',item['doi'],{'xsi:type':'dcterms:doi'})

        if 'media_content' in item and item['media_content'] is not None:
            handler.startElement('media:content',{'url':item['media_content']['url'],'type':'text/plain'})
            handler.addQuickElement('dcterms:isFormatOf',item['media_content']['link_url'])
            handler.endElement('media:content')

class RfcFeed(Feed):
    feed_type = Rss201WithNamespacesFeed
    title = "RFCs"
    author_name = "RFC Editor"
    link = "https://www.rfc-editor.org/rfc-index2.html"
    
    def items(self):
        cutoff = datetime.datetime.now() - datetime.timedelta(days=8)
        rfc_events = DocEvent.objects.filter(type='published_rfc',time__gte=cutoff).order_by('-time')
        results = [(e.doc, e.time) for e in rfc_events]
        for doc,time in results:
            doc.publication_time = time
        return [doc for doc,time in results]
    
    def item_title(self, item):
        return item.canonical_name()

    def item_description(self, item):
        return item.title

    def item_link(self, item):
        return "https://rfc-editor.org/info/%s"%item.canonical_name()

    def item_pubdate(self, item):
        return item.publication_time

    def item_extra_kwargs(self, item):
        extra = super(RfcFeed, self).item_extra_kwargs(item)
        extra.update({'dcterms_abstract': item.abstract})
        extra.update({'dcterms_accessRights': 'gratis'})
        extra.update({'dcterms_format': 'text/html'})
        extra.update({'media_content': {'url': 'https://rfc-editor.org/rfc/%s.txt' % item.canonical_name(),
                                        'link_url': self.item_link(item) 
                                       }
                     })
        extra.update({'doi':'http://dx.doi.org/10.17487/%s' % item.canonical_name().upper()})

        #TODO 
        # R104 Publisher (Mandatory - but we need a string from them first)

        #TODO MAYBE (Optional stuff)
        # R108 License
        # R115 Creator/Contributor (which would we use?)
        # F305 Checksum (do they use it?) (or should we put the our digital signature in here somewhere?)
        # F308 Holder of rights (copyright)

        # Stuff we can't do yet given what's in the datatracker
        # R118 Keyword

        return extra

