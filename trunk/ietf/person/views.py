import datetime

from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404

import debug                            # pyflakes:ignore

from ietf.person.models import Email, Person, Alias
from ietf.person.fields import select2_id_name_json

def ajax_select2_search(request, model_name):
    if model_name == "email":
        model = Email
    else:
        model = Person

    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = model.objects.none()
    else:
        query = Q()
        for t in q:
            if model == Email:
                query &= Q(person__alias__name__icontains=t) | Q(address__icontains=t)
            elif model == Person:
                if "@" in t: # allow searching email address if there's a @ in the search term
                    query &= Q(alias__name__icontains=t) | Q(email__address__icontains=t)
                else:
                    query &= Q(alias__name__icontains=t)

        objs = model.objects.filter(query)

    # require an account at the Datatracker
    only_users = request.GET.get("user") == "1"
    all_emails = request.GET.get("a", "0") == "1"

    if model == Email:
        objs = objs.exclude(person=None).order_by('person__name')        
        if not all_emails:
            objs = objs.filter(active=True)
        if only_users:
            objs = objs.exclude(person__user=None)
    elif model == Person:
        objs = objs.order_by("name")
        if only_users:
            objs = objs.exclude(user=None)

    try:
        page = int(request.GET.get("p", 1)) - 1
    except ValueError:
        page = 0

    objs = objs.distinct()[page:page + 10]

    return HttpResponse(select2_id_name_json(objs), content_type='application/json')

def profile(request, email_or_name):

    if '@' in email_or_name:
        persons = [ get_object_or_404(Email, address=email_or_name).person, ]
    else:
        aliases = Alias.objects.filter(name=email_or_name)
        persons = list(set([ a.person for a in aliases ]))
        if not persons:
            raise Http404
    return render(request, 'person/profile.html', {'persons': persons, 'today':datetime.date.today()})
