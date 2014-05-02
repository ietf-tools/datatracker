import os
import re

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.conf import settings
from django.http import HttpResponse

import changelog

def trac_links(text):
    # changeset links
    text = re.sub(r'\[(\d+)\]', r'<a href="http://wiki.tools.ietf.org/tools/ietfdb/changeset/\1">[\1]</a>', text)
    # issue links
    text = re.sub(r'#(\d+)', r'<a href="http://wiki.tools.ietf.org/tools/ietfdb/ticket/\1">#\1</a>', text)
    return text


def release(request, version=None):
    entries = {}
    if os.path.exists(settings.CHANGELOG_PATH):
        log_entries = changelog.parse(settings.CHANGELOG_PATH)
    else:
        return HttpResponse("Error: changelog file %s not found" % settings.CHANGELOG_PATH)
    next = None
    for entry in log_entries:
        if next:
            next.prev = entry
        entry.next = next
        next = entry
    entries = dict((entry.version, entry) for entry in log_entries)
    if version == None or version not in entries:
        version = log_entries[0].version        
    entries[version].logentry = trac_links(entries[version].logentry)
    return render_to_response('release/release.html', { 'releases': log_entries, 'version': version, 'entry': entries[version], }, context_instance=RequestContext(request))

