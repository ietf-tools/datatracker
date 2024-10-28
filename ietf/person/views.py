# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from io import StringIO, BytesIO
from PIL import Image

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.ietfauth.utils import role_required
from ietf.person.models import Email, Person
from ietf.person.fields import select2_id_name_json
from ietf.person.forms import MergeForm
from ietf.person.utils import handle_users, merge_persons, lookup_persons


def ajax_select2_search(request, model_name):
    if model_name == "email":
        model = Email
    else:
        model = Person

    q = [w.strip() for w in request.GET.get('q', '').split() if w.strip()]

    if not q:
        objs = model.objects.none()
    else:
        query = Q()  # all objects returned if no other terms in the queryset
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
    persons = lookup_persons(email_or_name)
    return render(request, 'person/profile.html', {'persons': persons, 'today': timezone.now()})


def photo(request, email_or_name):
    persons = lookup_persons(email_or_name)
    if len(persons) > 1:
        raise Http404("No photo found")
    person = persons[0]
    if not person.photo:
        raise Http404("No photo found")
    size = request.GET.get('s') or request.GET.get('size', '80')
    if not size.isdigit():
        return HttpResponse("Size must be integer", status=400)
    size = int(size)
    with Image.open(person.photo) as img:
        img = img.resize((size, img.height*size//img.width))
        bytes = BytesIO()
        try:
            img.save(bytes, format='JPEG')
            return HttpResponse(bytes.getvalue(), content_type='image/jpg')
        except OSError:
            raise Http404


@role_required("Secretariat")
def merge(request):
    form = MergeForm()
    method = 'get'
    change_details = ''
    warn_messages = []
    source = None
    target = None

    if request.method == "GET":
        form = MergeForm()
        if request.GET:
            form = MergeForm(request.GET)
            if form.is_valid():
                source = form.cleaned_data.get('source')
                target = form.cleaned_data.get('target')
                if source.user and target.user:
                    warn_messages.append('WARNING: Both Person records have logins.  Be sure to specify the record to keep in the Target field.')
                    if source.user.last_login and target.user.last_login and source.user.last_login > target.user.last_login:
                        warn_messages.append('WARNING: The most recently used login is being deleted!')
                change_details = handle_users(source, target, check_only=True)
                method = 'post'
            else:
                method = 'get'

    if request.method == "POST":
        form = MergeForm(request.POST)
        if form.is_valid():
            source = form.cleaned_data.get('source')
            source_id = source.id
            target = form.cleaned_data.get('target')
            # Do merge with force
            output = StringIO()
            success, changes = merge_persons(request, source, target, file=output)
            if success:
                messages.success(request, 'Merged {} ({}) to {} ({}). {})'.format(
                    source.name, source_id, target.name, target.id, changes))
            else:
                messages.error(request, output)
            return redirect('ietf.secr.rolodex.views.view', id=target.pk)

    return render(request, 'person/merge.html', {
        'form': form,
        'method': method,
        'change_details': change_details,
        'source': source,
        'target': target,
        'warn_messages': warn_messages,
    })
