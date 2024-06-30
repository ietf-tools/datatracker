# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import json
import datetime
from django.http import HttpResponse
from django.shortcuts import render
from ietf.status.models import Status

import debug                            # pyflakes:ignore

def get_context_data():
    status = Status.objects.order_by("-date").first()
    if status.active == False:
        return { "hasMessage": False }

    context = {
        "hasMessage": True,
        "id": status.status_id,
        "slug": status.slug,
        "title": status.message_title,
        "body": status.message,
        "url": status.url, # TODO derive this        
        "date": status.date.isoformat(),
        "by": status.by.name,
    }
    return context

def status_index(request):
    return render(request, "status/latest.html", context=get_context_data())

def status_index_json(request):
    return HttpResponse(json.dumps(get_context_data()), status=200, content_type='application/json')
