import json

from django.http import HttpResponse

def template(template):
    def decorator(fn):
        def render(request, *args, **kwargs):
            context_data = fn(request, *args, **kwargs)
            if isinstance(context_data, HttpResponse):
                # View returned an HttpResponse like a redirect
                return context_data
            else:
                # For any other type of data try to populate a template
                return render(request, template, context_data)
        return render
    return decorator

def jsonapi(fn):
    def to_json(request, *args, **kwargs):
        context_data = fn(request, *args, **kwargs)
        return HttpResponse(json.dumps(context_data),
                content_type='application/json')
    return to_json

