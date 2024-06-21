# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import json
import datetime
from django.http import HttpResponse
from django.shortcuts import render

import debug                            # pyflakes:ignore

def get_context_data():
    # TODO: get latest status message from model
    context = {
        "message": "what",
        "url": "https://html5zombo.com/",
        "date": datetime.datetime.now().isoformat(),
        "by": "Joe Bob Briggs"
    }
    return context

def status_index(request):
    return render(request, "status/index.html", context=get_context_data())

def status_index_json(request):
    return HttpResponse(json.dumps(get_context_data()), status=200, content_type='application/json')
