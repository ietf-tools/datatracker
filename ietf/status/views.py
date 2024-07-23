# Copyright The IETF Trust 2016-2024, All Rights Reserved
# -*- coding: utf-8 -*-

import json
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from ietf.utils import markdown
from django.shortcuts import render, get_object_or_404
from ietf.status.models import Status

import debug                            # pyflakes:ignore

def get_context_data():
    status = Status.objects.filter(active=True).order_by("-date").first()
    if status is None:
        return { "hasMessage": False }

    context = {
        "hasMessage": True,
        "id": status.id,
        "slug": status.slug,
        "title": status.title,
        "body": status.body,
        "url": f"/status/{status.slug}",
        "date": status.date.isoformat()
    }
    return context

def status_latest_html(request):
    return render(request, "status/latest.html", context=get_context_data())

def status_page(request, slug):
    sanitised_slug = slug.rstrip("/")
    status = get_object_or_404(Status, slug=sanitised_slug)
    return render(request, "status/status.html", context={
        'status': status,
        'status_page_html': markdown.markdown(status.page or ""),
    })

def status_latest_json(request):
    return HttpResponse(json.dumps(get_context_data()), status=200, content_type='application/json')

def status_latest_redirect(request):
    context = get_context_data()
    if context["hasMessage"] == True:
        return HttpResponseRedirect(context["url"])
    return HttpResponseNotFound()
