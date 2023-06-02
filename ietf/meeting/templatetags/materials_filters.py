# Copyright The IETF Trust 2023, All Rights Reserved
from django import template

import debug       # pyflakes:ignore
import itertools

register = template.Library()

def _uniq(l):
    # https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6
    l = list(dict.fromkeys(l))
    # Filter out None return values from Session.agendas() etc.
    # Listify the result, because the template calls length() on it.
    return list(itertools.filterfalse(lambda x: not x, l))

def _flatten(ll):
    return [x for l in ll for x in l]

@register.filter
def all_meeting_sessions_cancelled(ss):
    return set(s.current_status for s in ss) == {'canceled'}

@register.filter
def all_meeting_agendas(ss):
    return _uniq([s.agenda() for s in ss])

@register.filter
def all_meeting_minutes(ss):
    return _uniq([s.minutes() for s in ss])

@register.filter
def all_meeting_bluesheets(ss):
    return _uniq(_flatten([s.bluesheets() for s in ss]))

@register.filter
def all_meeting_recordings(ss):
    return _uniq(_flatten([s.recordings() for s in ss]))

@register.filter
def all_meeting_slides(ss):
    return _uniq(_flatten([s.slides() for s in ss]))

@register.filter
def all_meeting_drafts(ss):
    return _uniq(_flatten([s.drafts() for s in ss]))

@register.filter
def timesort(ss):
    return sorted(ss, key=lambda s: s.official_timeslotassignment().timeslot.time)
