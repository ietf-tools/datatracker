from django.http import Http404, HttpResponse

from ietf.person.models import *
from ietf.person.forms import json_emails

def ajax_search_emails(request):
    emails = Email.objects.filter(person__alias__name__icontains=request.GET.get('q','')).filter(active='true').order_by('person__name').distinct()[:10]
    return HttpResponse(json_emails(emails), mimetype='application/json')
