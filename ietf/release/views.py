import os
import re
import json
import datetime
import gzip

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.conf import settings
from django.http import HttpResponse

import changelog

# workaround for thread import lock problem, http://bugs.python.org/issue7980
import time                             
time.strptime('1984', '%Y')             # this will happen lazily when changelog calls tzparse later, otherwise


# workaround for thread import lock problem, http://bugs.python.org/issue7980
import time
time.strptime('1984', '%Y')

def trac_links(text):
    # changeset links
    text = re.sub(r'\[(\d+)\]', r'<a href="https://wiki.tools.ietf.org/tools/ietfdb/changeset/\1">[\1]</a>', text)
    # issue links
    text = re.sub(r'#(\d+)', r'<a href="https://wiki.tools.ietf.org/tools/ietfdb/ticket/\1">#\1</a>', text)
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
    entries[version].logentry = trac_links(entries[version].logentry.strip('\n'))

    code_coverage_url = None
    code_coverage_time = None
    if os.path.exists(settings.TEST_CODE_COVERAGE_REPORT_FILE) and version == log_entries[0].version:
        code_coverage_url = settings.TEST_CODE_COVERAGE_REPORT_URL
        code_coverage_time = datetime.datetime.fromtimestamp(os.path.getmtime(settings.TEST_CODE_COVERAGE_REPORT_FILE))

    coverage = {}
    if os.path.exists(settings.TEST_COVERAGE_MASTER_FILE):
        if settings.TEST_COVERAGE_MASTER_FILE.endswith(".gz"):
            with gzip.open(settings.TEST_COVERAGE_MASTER_FILE, "rb") as file:
                coverage_data = json.load(file)
        else:
            with open(settings.TEST_COVERAGE_MASTER_FILE) as file:
                coverage_data = json.load(file)
        if version in coverage_data:
            coverage = coverage_data[version]
            for key in coverage:
                if "coverage" in coverage[key]:
                    coverage[key]["percentage"] = coverage[key]["coverage"] * 100

    return render_to_response('release/release.html',
        {
            'releases': log_entries,
            'version': version,
            'entry': entries[version],
            'coverage': coverage,
            'code_coverage_url': code_coverage_url,
            'code_coverage_time': code_coverage_time,
        },
        context_instance=RequestContext(request))

    
