from django.http import Http404, HttpResponse

from ietf.person.models import *
from ietf.person.forms import json_emails

def ajax_search_emails(request):
    emails = Email.objects.filter(person__alias__name__istartswith=request.GET.get('q','')).order_by('person__name').distinct()
    return HttpResponse(json_emails(emails), mimetype='application/json')
