# Copyright The IETF Trust 2010, All Rights Reserved

from django.http import HttpResponse
from django.shortcuts import render_to_response as render, get_object_or_404
from django.template import RequestContext

def settings(request, new_enough = -1, expires_soon = -1):
    if new_enough < 0:
        if "new_enough" in request.COOKIES:
            new_enough = int(request.COOKIES["new_enough"])
        else:
            new_enough = 14
    if expires_soon < 0:
        if "expires_soon" in request.COOKIES:
            expires_soon = int(request.COOKIES["expires_soon"])
        else:
            expires_soon = 14
    return render("cookies/settings.html",
           {
            "new_enough" : new_enough,
            "expires_soon" : expires_soon
            }, context_instance=RequestContext(request))

def new_enough(request, days="14"):
    try:
        days = int(days)
    except:
        days = 0
    if days == 0:
        days = 14
    response = settings(request, days, -1)
    response.set_cookie("new_enough", days)
    return response

def expires_soon(request, days="14"):
    try:
        days = int(days)
    except:
        days = 0
    if days == 0:
        days = 14
    response = settings(request, -1, days)
    response.set_cookie("expires_soon", days)
    return response
