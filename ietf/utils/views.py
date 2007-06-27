# Copyright The IETF Trust 2007, All Rights Reserved

from django.shortcuts import render_to_response as render

testurls = []
urlcount = 0
hash2url = {}
num2hash = {}
hash2num = {}
host = "merlot.tools.ietf.org:31415"

def get_info(page):
    global testurls
    global hash2url
    global num2hash
    global hash2num
    global urlcount
    if not testurls:
        from ietf.tests import get_testurls
        testurls = [ tuple for tuple in get_testurls() if tuple[2] and "200" in tuple[0] ]
        urlcount  = len(testurls)
        num2hash = dict([ (i, "%x"% (testurls[i][1].__hash__() +0x80000000)) for i in range(urlcount)])
        hash2url = dict([ (num2hash[i], testurls[i][1]) for i in range(urlcount)])
        hash2num = dict([ (num2hash[num], num) for num in num2hash ])

    info = {}
    try:
        page = int(page)
    except:
        pass
    if page in num2hash:
        page = num2hash[page]
    if not page in hash2url:
        page = num2hash[0]
    hash = page
    assert(hash not in num2hash)
    num = hash2num[hash]
    info["next"] = num2hash[ (num + 1) % urlcount ]
    info["this"] = hash
    info["prev"] = num2hash[ (num - 1 + urlcount) % urlcount ]
    info["new"]  = "http://%s/%s" % (host, testurls[num][1][1:])
    info["old"]  = testurls[num][2]
    return info

def review(request, page=0, panes=None):
        return render("utils/frame2.html", {"info": get_info(page) })

def top(request, page=0):
    return render("utils/review.html", {"info": get_info(page) })

def all(request):
    get_info(0)                         # prime the list
    info = []
    for i in range(urlcount):
        item = {}
        item["num"] = num2hash[i]
        item["new"] = testurls[i][1]
        item["old"] = testurls[i][2]
        info.append(item)
        
    return render("utils/all.html", {"info": info, "count": len(info) })