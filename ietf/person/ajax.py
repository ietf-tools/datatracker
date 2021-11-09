import json

from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from ietf.ietfauth.utils import role_required
from ietf.person.models import Person

@role_required('Secretariat')
def person_email_json(request, personid):
    person = get_object_or_404(Person, pk=personid)
    addresses = person.email_set.order_by('-primary').values('address', 'primary')

    return HttpResponse(json.dumps(list(addresses)), content_type='application/json')