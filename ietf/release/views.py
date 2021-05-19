# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
import re
import json
import datetime
import gzip
from tzparse import tzparse
from calendar import timegm

from django.shortcuts import render
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.html import escape
from django.utils.safestring import mark_safe

import changelog
import debug                            # pyflakes:ignore

# workaround for thread import lock problem, http://bugs.python.org/issue7980
import time                             
time.strptime('1984', '%Y')             # we do this to force lib loading, instead of it happening lazily when changelog calls tzparse later


def trac_links(text):
    # changeset links
    text = re.sub(r'\[(\d+)\]', r'<a href="https://trac.ietf.org/trac/ietfdb/changeset/\1">[\1]</a>', text)
    # issue links
    text = re.sub(r'([^&])#(\d+)', r'\1<a href="https://trac.ietf.org/trac/ietfdb/ticket/\2">#\2</a>', text)
    return text


def get_coverage_data():
    cache_key = 'release:get_coverage_data'
    coverage_data = cache.get(cache_key)
    if not coverage_data:
        coverage_data = {}
        if os.path.exists(settings.TEST_COVERAGE_MASTER_FILE):
            if settings.TEST_COVERAGE_MASTER_FILE.endswith(".gz"):
                with gzip.open(settings.TEST_COVERAGE_MASTER_FILE, "rb") as file:
                    coverage_data = json.load(file)
            else:
                with io.open(settings.TEST_COVERAGE_MASTER_FILE) as file:
                    coverage_data = json.load(file)
        cache.set(cache_key, coverage_data, 60*60*24)
    return coverage_data

def get_changelog_entries():
    cache_key = 'release:get_changelog_entries'
    log_entries = cache.get(cache_key)
    if not log_entries:
        if os.path.exists(settings.CHANGELOG_PATH):
            log_entries = changelog.parse(settings.CHANGELOG_PATH)
            cache.set(cache_key, log_entries, 60*60*24)
    return log_entries

entries = None
log_entries = None
coverage_data = None
def release(request, version=None):
    global entries, log_entries, coverage_data
    if not entries:
        log_entries = get_changelog_entries()
        if not log_entries:
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
    if not hasattr(entries[version], 'html'):
        entries[version].html = trac_links(escape(entries[version].logentry.strip('\n')))

    code_coverage_url = None
    code_coverage_time = None
    if os.path.exists(settings.TEST_CODE_COVERAGE_REPORT_FILE) and version == log_entries[0].version:
        code_coverage_url = settings.TEST_CODE_COVERAGE_REPORT_URL
        code_coverage_time = datetime.datetime.fromtimestamp(os.path.getmtime(settings.TEST_CODE_COVERAGE_REPORT_FILE))

    coverage = {}
    if not coverage_data:
        coverage_data = get_coverage_data()
    if version in coverage_data:
        coverage = coverage_data[version]
        for key in coverage:
            if "coverage" in coverage[key]:
                coverage[key]["percentage"] = coverage[key]["coverage"] * 100

    return render(request, 'release/release.html',
        {
            'releases': log_entries,
            'version': version,
            'entry': entries[version],
            'coverage': coverage,
            'code_coverage_url': code_coverage_url,
            'code_coverage_time': code_coverage_time,
        } )


def stats(request):

    coverage_chart_data = []
    frequency_chart_data = []

    coverage_data = get_coverage_data()
    coverage_series_data = {}
    for version in coverage_data:
        if 'time' in coverage_data[version]:
            t = coverage_data[version]['time']
            secs = timegm(tzparse(t, "%Y-%m-%dT%H:%M:%SZ").timetuple()) * 1000
            for coverage_type in coverage_data[version]:
                if 'coverage' in coverage_data[version][coverage_type]:
                    cov = round(coverage_data[version][coverage_type]['coverage'], 3)
                    if not coverage_type in coverage_series_data:
                        coverage_series_data[coverage_type] = []
                    coverage_series_data[coverage_type].append([secs, cov])

    for coverage_type in coverage_series_data:
        coverage_series_data[coverage_type].sort()
        # skip some early values
        coverage_series_data[coverage_type] = coverage_series_data[coverage_type][2:]
        coverage_chart_data.append({
            'data': coverage_series_data[coverage_type],
            'name': coverage_type,
        })

    log_entries = get_changelog_entries()
    frequency = {}
    frequency_series_data = []
    for entry in log_entries:
        year = entry.time.year
        if not year in frequency:
            frequency[year] = 0
        frequency[year] += 1
    for year in frequency:
        frequency_series_data.append([year, frequency[year]])
    frequency_series_data.sort()
    frequency_chart_data.append({
        'data': frequency_series_data,
        'name': 'Releases',
    })

    return render(request, 'release/stats.html',
        {
            'coverage_chart_data': mark_safe(json.dumps(coverage_chart_data)),
            'frequency_chart_data': mark_safe(json.dumps(frequency_chart_data)),
        })
