# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


'''
proc_utils.py

This module contains all the functions for generating static proceedings pages
'''
import datetime
from urllib.parse import urlencode

import debug        # pyflakes:ignore

from django.conf import settings

from ietf.meeting.models import Meeting, SchedTimeSessAssignment
from ietf.utils.timezone import make_aware


def _get_session(number,name,date,time):
    '''Lookup session using data from video title'''
    meeting = Meeting.objects.get(number=number)
    timeslot_time = make_aware(datetime.datetime.strptime(date + time,'%Y%m%d%H%M'), meeting.tz())
    try:
        assignment = SchedTimeSessAssignment.objects.get(
            schedule__in = [meeting.schedule, meeting.schedule.base],
            session__group__acronym = name.lower(),
            timeslot__time = timeslot_time,
        )
    except (SchedTimeSessAssignment.DoesNotExist, SchedTimeSessAssignment.MultipleObjectsReturned):
        return None

    return assignment.session

def _get_urls_from_json(doc):
    '''Returns list of dictionary title,url from search results'''
    urls = []
    for item in doc['items']:
        title = item['snippet']['title']
        #params = dict(v=item['snippet']['resourceId']['videoId'], list=item['snippet']['playlistId'])
        params = [('v',item['snippet']['resourceId']['videoId']), ('list',item['snippet']['playlistId'])]
        url = settings.YOUTUBE_BASE_URL + '?' + urlencode(params)
        urls.append(dict(title=title, url=url))
    return urls
