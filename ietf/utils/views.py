from django.shortcuts import render_to_response as render

testurls = []
urlcount = 0
host = "merlot.tools.ietf.org:31415"

def get_info(page):
    global testurls
    global urlcount
    if not testurls:
        from ietf.tests import get_testurls
        testurls = [ tuple for tuple in get_testurls() if tuple[2] and "200" in tuple[0] ]
        urlcount  = len(testurls)
    info = {}
    page = int(page)
    if not page in range(urlcount):
        page = 0
    info["next"] = (page + 1) % urlcount
    info["this"] = page
    info["prev"] = (page - 1 + urlcount) % urlcount
    info["new"]  = "http://%s/%s" % (host, testurls[page][1][1:])
    info["old"]  = testurls[page][2]
    return info

def review(request, page=0, panes=None):
        return render("utils/frame2.html", {"info": get_info(page) })

def top(request, page=None):
    return render("utils/review.html", {"info": get_info(page) })

def all(request):
    get_info(0)                         # prime the list
    info = []
    for i in range(urlcount):
        item = {}
        item["num"] = i
        item["new"] = testurls[i][1]
        item["old"] = testurls[i][2]
        info.append(item)
        
    return render("utils/all.html", {"info": info })