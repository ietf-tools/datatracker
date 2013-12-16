import datetime
import logging
import sys
import json

from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, Http404

from dajaxice.core import dajaxice_functions
from dajaxice.decorators import dajaxice_register

from ietf.person.models import Person

def person_json(request, personid):
    person = get_object_or_404(Person, pk=personid)

    return HttpResponse(json.dumps(person.json_dict(request.build_absolute_uri("/")),
                                   sort_keys=True, indent=2),
                        content_type="text/json")

