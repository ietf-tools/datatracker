from django.http import HttpResponse
from django.db.models import Q

from ietf.person.models import Email
from ietf.person.fields import json_emails

def ajax_search_emails(request):
    q = request.GET.get('q', '').strip()
    emails = Email.objects.filter(Q(person__alias__name__icontains=q) |
                                  Q(address__icontains=q)).filter(active='true').order_by('person__name').distinct()[:10]
    return HttpResponse(json_emails(emails), content_type='application/json')
