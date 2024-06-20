# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.shortcuts import render

import debug                            # pyflakes:ignore

def status_index(request):
    return render(request, "status/index.html")

def status_api(request):
    return HttpResponse(response, status=200, content_type='application/json')
