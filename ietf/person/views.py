from django.http import HttpResponse
from django.db.models import Q

from ietf.person.models import Email
from ietf.person.fields import json_emails

def ajax_search_emails(request):
    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]
    if not q:
        emails = Email.objects.none()
    else:
        query = Q()
        for t in q:
            query &= Q(person__alias__name__icontains=t) | Q(address__icontains=t)

        emails = Email.objects.filter(query).exclude(person=None)

    if request.GET.get("user") == "1":
        emails = emails.exclude(person__user=None) # require an account at the Datatracker

    emails = emails.filter(active=True).order_by('person__name').distinct()[:10]
    return HttpResponse(json_emails(emails), content_type='application/json')
