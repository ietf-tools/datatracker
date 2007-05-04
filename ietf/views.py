from django.shortcuts import render_to_response as render
import urls
import re

def apps(request):
    paths = []
    for pattern in urls.urlpatterns:
        path = pattern.regex.pattern.split("/")[0][1:]
        if not re.search("[^a-z]", path) and not path in ["my", "feeds"]:
            paths.append(path)
    apps = list(set(paths))
    apps.sort()
    return render("apps.html", {"apps": apps })