import re
import os

from django.template import RequestContext
from django.shortcuts import render_to_response

import changelog

def release(request, version=None):
    entries = {}
    log_entries = changelog.parse("changelog")
    next = None
    for entry in log_entries:
        if next:
            next.prev = entry
        entry.next = next
        next = entry
    entries = dict([ (entry.version, entry) for entry in log_entries])
    if version == None:
        version = log_entries[0].version        
    return render_to_response('release/release.html', { 'entry': entries[version], }, context_instance=RequestContext(request))

