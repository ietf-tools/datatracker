try:
    import json
except ImportError:
    import simplejson as json

from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response

def template(template):
    def decorator(fn):
        def render(request, *args, **kwargs):
            context_data = fn(request, *args, **kwargs)
            if isinstance(context_data, HttpResponse):
                # View returned an HttpResponse like a redirect
                return context_data
            else:
                # For any other type of data try to populate a template
                return render_to_response(template,
                        context_data,
                        context_instance=RequestContext(request)
                    )
        return render
    return decorator

def jsonapi(fn):
    def to_json(request, *args, **kwargs):
        context_data = fn(request, *args, **kwargs)
        return HttpResponse(json.dumps(context_data),
                mimetype='application/json')
    return to_json

def render(template, data, request):
    return render_to_response(template,
                              data,
                              context_instance=RequestContext(request))
