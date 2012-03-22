# Copyright The IETF Trust 2011, All Rights Reserved

from django.conf import settings
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse as urlreverse
from ietf.utils.history import find_history_active_at

from ietf.group.models import Group
from ietf.wgcharter.views import _get_history, _get_html
from ietf.wgcharter import markup_txt
import datetime
import re, os

class GroupComments(Feed):
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
                    os.path.join(dh.get_file_path(), dh.name+"-"+dh.rev+".txt"))
            else:
                h['rev'] = obj.charter.rev
                h['charter'] = _get_html(
                    "charter-ietf-"+str(obj.acronym)+"-"+str(obj.charter.rev)+",html", 
                    os.path.join(obj.charter.get_file_path(), "charter-ietf-"+obj.acronym+"-"+obj.charter.rev+".txt"))
        return history

    def item_link(self, obj):
        return urlreverse('wg_charter', kwargs={'acronym': obj['group'].acronym})

    def item_pubdate(self, obj):
	return obj['date']


