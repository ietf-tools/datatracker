# Copyright The IETF Trust 2010, All Rights Reserved

from django.shortcuts import render_to_response as render
from django.template import RequestContext

def settings(request, new_enough = -1, expires_soon = -1, full_draft = "", left_menu=""):
    if new_enough < 0:
        if "new_enough" in request.COOKIES and request.COOKIES["new_enough"].isdigit():
            new_enough = int(request.COOKIES["new_enough"])
        else:
            new_enough = 14
    if expires_soon < 0:
        if "expires_soon" in request.COOKIES and request.COOKIES["expires_soon"].isdigit():
            expires_soon = int(request.COOKIES["expires_soon"])
        else:
            expires_soon = 14
    if full_draft == "":
        if "full_draft" in request.COOKIES:
            full_draft = request.COOKIES["full_draft"]
            if full_draft != 'on' and full_draft != 'off':
                full_draft = "off"
        else:
            full_draft = "off"
    if left_menu == "":
        if "left_menu" in request.COOKIES:
            left_menu = request.COOKIES["left_menu"]
            if left_menu != 'on' and left_menu != 'off':
                left_menu = "on"
        else:
            left_menu = "on"
    return render("cookies/settings.html",
           {
            "new_enough" : new_enough,
            "expires_soon" : expires_soon,
            "full_draft" : full_draft,
            "left_menu": left_menu,
            }, context_instance=RequestContext(request))

def new_enough(request, days="14"):
    try:
        days = int(days)
    except:
        days = 0
    if days == 0:
        days = 14
    response = settings(request, new_enough=days)
    response.set_cookie("new_enough", days, 315360000)
    return response

def expires_soon(request, days="14"):
    try:
        days = int(days)
    except:
        days = 0
    if days == 0:
        days = 14
    response = settings(request, expires_soon=days)
    response.set_cookie("expires_soon", days, 315360000)
    return response

def full_draft(request, enabled="off"):
    if enabled != "on" and enabled != "off":
        enabled = "off"
    response = settings(request, full_draft=enabled)
    response.set_cookie("full_draft", enabled, 315360000)
    return response

def left_menu(request, enabled="on"):
    if enabled != "on" and enabled != "off":
        enabled = "on"
    # Propagate the new setting immediately, to render the settings page
    # iteself according to the setting:
    request.COOKIES["left_menu"] = enabled 
    response = settings(request, left_menu=enabled)
    response.set_cookie("left_menu", enabled, 315360000)
    return response

