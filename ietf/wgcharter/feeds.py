# Copyright The IETF Trust 2011, All Rights Reserved

import datetime, re, os

from django.conf import settings
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse as urlreverse
from django.template.defaultfilters import truncatewords_html

from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill
from ietf.wgcharter.utils import *
from ietf.utils.history import find_history_active_at
from ietf.group.models import Group
from ietf.idrfc.views_doc import _get_html

def _get_history(wg, versions=None):
    results = []
    for e in wg.charter.docevent_set.all().order_by('-time'):
        info = {}
        charter_history = find_history_active_at(wg.charter, e.time)
        info['version'] = charter_history.rev if charter_history else wg.charter.rev
        info['text'] = e.desc
        info['by'] = e.by.plain_name()
        info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
        info['snipped'] = info['textSnippet'][-3:] == "..."
        if e.type == "new_revision":
            if charter_history:
                charter = get_charter_for_revision(wg.charter, charter_history.rev)
                group = get_group_for_revision(wg, charter_history.rev)
            else:
                charter = get_charter_for_revision(wg.charter, wg.charter.rev)
                group = get_group_for_revision(wg, wg.charter.rev)

            if versions:
                vl = [x['rev'] for x in versions]
                if vl:
                    prev_charter = get_charter_for_revision(wg.charter, vl[vl.index(charter.rev) - 1])
            else:
                prev_charter = get_charter_for_revision(wg.charter, prev_revision(charter.rev))
            prev_group = get_group_for_revision(wg, prev_revision(charter.rev))
            results.append({'comment':e, 'info':info, 'date':e.time, 'group': group,
                            'charter': charter, 'prev_charter': prev_charter,
                            'prev_group': prev_group,
                            'txt_url': settings.CHARTER_TXT_URL,
                            'is_rev':True})
        else:
            results.append({'comment':e, 'info':info, 'date':e.time, 'group': wg, 'is_com':True})

    # convert plain dates to datetimes (required for sorting)
    for x in results:
        if not isinstance(x['date'], datetime.datetime):
            if x['date']:
                x['date'] = datetime.datetime.combine(x['date'], datetime.time(0,0,0))
            else:
                x['date'] = datetime.datetime(1970,1,1)

    results.sort(key=lambda x: x['date'])
    results.reverse()
    return results

class GroupEvents(Feed):
    feed_type = Atom1Feed
    title_template = "feeds/wg_charter_title.html"
    description_template = "feeds/wg_charter_description.html"
    def get_object(self, bits):
	if len(bits) != 1:
	    raise Group.DoesNotExist
        return Group.objects.get(acronym=bits[0])

    def title(self, obj):
        return "WG changes for %s" % obj.acronym

    def link(self, obj):
	if not obj:
	    raise FeedDoesNotExist
	return urlreverse('wg_charter', kwargs={'acronym': obj.acronym})

    def description(self, obj):
	return self.title(obj)

    def items(self, obj):
        history = _get_history(obj)
        for h in history:
            gh = find_history_active_at(obj, h['date'])
            if gh:
                h['chairs'] = [x.person.plain_name() for x in gh.rolehistory_set.filter(name__slug="chair")]
                h['secr'] = [x.person.plain_name() for x in gh.rolehistory_set.filter(name__slug="secr")]
                h['techadv'] = [x.person.plain_name() for x in gh.rolehistory_set.filter(name__slug="techadv")]
            else:
                h['chairs'] = [x.person.plain_name() for x in obj.role_set.filter(name__slug="chair")]
                h['secr'] = [x.person.plain_name() for x in obj.role_set.filter(name__slug="secr")]
                h['techadv'] = [x.person.plain_name() for x in obj.role_set.filter(name__slug="techadv")]
            dh = find_history_active_at(obj.charter, h['date'])
            if dh:
                h['rev'] = dh.rev
                h['charter'] = _get_html(
                    str(dh.name)+"-"+str(dh.rev)+",html", 
                    os.path.join(dh.get_file_path(), dh.name+"-"+dh.rev+".txt"), False)
            else:
                h['rev'] = obj.charter.rev
                h['charter'] = _get_html(
                    "charter-ietf-"+str(obj.acronym)+"-"+str(obj.charter.rev)+",html", 
                    os.path.join(obj.charter.get_file_path(), "charter-ietf-"+obj.acronym+"-"+obj.charter.rev+".txt"), False)
        return history

    def item_link(self, obj):
        return urlreverse('wg_charter', kwargs={'acronym': obj['group'].acronym})

    def item_pubdate(self, obj):
	return obj['date']


