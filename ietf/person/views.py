# Copyright The IETF Trust 2012-2025, All Rights Reserved
# -*- coding: utf-8 -*-


from io import StringIO, BytesIO
from PIL import Image

from django.conf import settings
from django.contrib import messages
from django.core.cache import caches
from django.db.models import Count, Q
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.doc.models import DocEvent, RelatedDocument
from ietf.ietfauth.utils import role_required
from ietf.person.models import Email, Person
from ietf.person.fields import select2_id_name_json
from ietf.person.forms import MergeForm, MergeRequestForm
from ietf.person.utils import (
    get_person_uuid_object,
    handle_users,
    lookup_persons,
    merge_persons,
)
from ietf.utils.mail import send_mail_text
from ietf.utils.timezone import RPC_TZINFO

REFERENCE_RELATIONSHIPS = ("refnorm", "refinfo", "refunk", "refold")


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
    PAGE_SIZE = 10
    first_item = page * PAGE_SIZE
    objs = objs.distinct()[first_item:first_item + PAGE_SIZE]

    return HttpResponse(select2_id_name_json(objs), content_type='application/json')


def rfc_rows(persons):
    """Build the RFC table rows for each person

    Returns a dict keyed on person pk. The columns are gathered for every person at
    once - read one at a time off the Document, each row costs a query per column.
    """
    rfcs = {p.pk: p.rfcs() for p in persons}
    rfc_ids = {d.pk for docs in rfcs.values() for d in docs}

    # The references of the draft an RFC was published from count as the RFC's own.
    draft_of = dict(
        RelatedDocument.objects.filter(
            target_id__in=rfc_ids, relationship="became_rfc"
        ).values_list("target_id", "source_id")
    )
    referenced_by = dict(
        RelatedDocument.objects.filter(
            target_id__in=rfc_ids | set(draft_of.values()),
            relationship__in=REFERENCE_RELATIONSHIPS,
            source__type__slug="rfc",
        )
        .values("target_id")
        .annotate(count=Count("id"))
        .values_list("target_id", "count")
    )

    # Matches Document.latest_event ordering, so the first row seen for a document
    # is the one its pub_date would have reported.
    published = {}
    for doc_id, time in (
        DocEvent.objects.filter(doc_id__in=rfc_ids, type="published_rfc")
        .order_by("-time", "-id")
        .values_list("doc_id", "time")
    ):
        published.setdefault(doc_id, time)

    return {
        pk: [
            {
                "doc": doc,
                "pub_date": (
                    published[doc.pk].astimezone(RPC_TZINFO).date()
                    if doc.pk in published
                    else None
                ),
                "referenced_by": referenced_by.get(doc.pk, 0)
                + referenced_by.get(draft_of.get(doc.pk), 0),
            }
            for doc in docs
        ]
        for pk, docs in rfcs.items()
    }


def profile_data(persons):
    """Build everything person/profile.html renders for each of persons"""
    rfcs = rfc_rows(persons)
    expired = {p.pk: list(p.expired_drafts().prefetch_related("states")) for p in persons}
    replaced = set(
        RelatedDocument.objects.filter(
            target_id__in={d.pk for docs in expired.values() for d in docs},
            relationship="replaces",
        ).values_list("target_id", flat=True)
    )

    profiles = []
    for person in persons:
        # Role.Meta orders by name_id alone, which leaves ties to the query plan.
        roles = sorted(
            person.role_set.select_related("name", "group", "email"),
            key=lambda r: (r.name_id, r.group.acronym),
        )
        profiles.append(
            {
                "person": person,
                "has_roles": bool(roles),
                "roles": [
                    r
                    for r in roles
                    if r.group.state_id in ["active", "bof"]
                    and r.group.acronym != "secretariat"
                ],
                "ext_resources": list(
                    person.personextresource_set.select_related("name")
                ),
                "rfcs": rfcs[person.pk],
                "active_drafts": list(
                    person.active_drafts().prefetch_related("states")
                ),
                "expired_drafts": [
                    d for d in expired[person.pk] if d.pk not in replaced
                ],
                "has_drafts": person.has_drafts(),
            }
        )
    return profiles


def profile_sections(persons):
    """Render each person's part of the profile page

    The rendered sections are cached, so a repeat view of a profile - including the
    revalidation a conditional request makes - costs neither the queries nor the
    render. Nothing in a section is tied to the moment it was rendered, so how stale
    one can be is entirely PERSON_PROFILE_CACHE_SECONDS.
    """
    slowpages = caches["slowpages"]
    keys = {person.pk: f"person:profile:{person.pk}" for person in persons}
    sections = slowpages.get_many(list(keys.values()))

    uncached = [person for person in persons if keys[person.pk] not in sections]
    for profile in profile_data(uncached):
        person = profile["person"]
        section = {
            "id": person.pk,
            "name": str(person),
            "has_drafts": profile["has_drafts"],
            "html": render_to_string("person/profile_body.html", {"profile": profile}),
        }
        slowpages.set(keys[person.pk], section, settings.PERSON_PROFILE_CACHE_SECONDS)
        sections[keys[person.pk]] = section

    return [sections[keys[person.pk]] for person in persons]


def profile(request, email_or_name):
    persons = lookup_persons(email_or_name)
    return render(
        request, "person/profile.html", {"sections": profile_sections(persons)}
    )


def profile_by_uuid(request, uuid):
    person_uuid = get_person_uuid_object(uuid)
    if person_uuid is None:
        raise Http404("No such person identifier")
    if not person_uuid.primary:
        # Self-heal a link that predates a merge by sending it to the canonical address.
        return redirect(
            "ietf.person.views.profile_by_uuid",
            uuid=person_uuid.person.primary_uuid,
        )
    return render(
        request,
        "person/profile.html",
        {"sections": profile_sections([person_uuid.person])},
    )


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
    return render(request, 'person/merge.html', {'form': form})


@role_required("Secretariat")
def merge_submit(request):
    change_details = ''
    warn_messages = []
    source = None
    target = None

    if request.method == "GET":
        if request.GET:
            form = MergeForm(request.GET, readonly=True)
            if form.is_valid():
                source = form.cleaned_data.get('source')
                target = form.cleaned_data.get('target')
                if source.user and target.user:
                    warn_messages.append('WARNING: Both Person records have logins.  Be sure to specify the record to keep in the Target field.')
                    if source.user.last_login and target.user.last_login and source.user.last_login > target.user.last_login:
                        warn_messages.append('WARNING: The most recently used login is being deleted!')
                change_details = handle_users(source, target, check_only=True)

    if request.method == "POST":
        form = MergeForm(request.POST, readonly=True)
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

    return render(request, 'person/merge_submit.html', {
        'form': form,
        'change_details': change_details,
        'source': source,
        'target': target,
        'warn_messages': warn_messages,
    })


@role_required("Secretariat")
def send_merge_request(request):
    if request.method == 'GET':
        merge_form = MergeForm(request.GET)
        if merge_form.is_valid():
            source = merge_form.cleaned_data['source']
            target = merge_form.cleaned_data['target']
            to = []
            if source.email():
                to.append(source.email().address)
            if target.email():
                to.append(target.email().address)
            if source.user:
                source_account = source.user.username
            else:
                source_account = source.email()
            if target.user:
                target_account = target.user.username
            else:
                target_account = target.email()
            sender_name = request.user.person.name
            subject = 'Action requested: Merging possible duplicate IETF Datatracker accounts'
            context = {
                'source_account': source_account,
                'target_account': target_account,
                'sender_name': sender_name,
            }
            body = render_to_string('person/merge_request_email.txt', context)
            initial = {
                'to': ', '.join(to),
                'frm': settings.DEFAULT_FROM_EMAIL,
                'reply_to': 'support@ietf.org',
                'subject': subject,
                'body': body,
                'by': request.user.person.pk,
            }
            form = MergeRequestForm(initial=initial)
        else:
            messages.error(request, "Error requesting merge email: " + merge_form.errors.as_text())
            return redirect("ietf.person.views.merge")

    if request.method == 'POST':
        form = MergeRequestForm(request.POST)
        if form.is_valid():
            extra = {"Reply-To": form.cleaned_data.get("reply_to")}
            send_mail_text(
                request,
                form.cleaned_data.get("to"),
                form.cleaned_data.get("frm"),
                form.cleaned_data.get("subject"),
                form.cleaned_data.get("body"),
                extra=extra,
            )

            messages.success(request, "The merge confirmation email was sent.")
            return redirect("ietf.person.views.merge")

    return render(request, "person/send_merge_request.html", {
        "form": form,
    })
