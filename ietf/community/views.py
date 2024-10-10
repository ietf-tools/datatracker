# Copyright The IETF Trust 2012-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import csv
import datetime
import json
import uuid

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.html import strip_tags

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, EmailSubscription, SearchRule
from ietf.community.forms import SearchRuleTypeForm, SearchRuleForm, AddDocumentsForm, SubscriptionForm
from ietf.community.utils import can_manage_community_list
from ietf.community.utils import docs_tracked_by_community_list, docs_matching_community_list_rule
from ietf.community.utils import states_of_significant_change, reset_name_contains_index_for_rule
from ietf.group.models import Group
from ietf.doc.models import DocEvent, Document
from ietf.doc.utils_search import prepare_document_table
from ietf.person.utils import lookup_persons
from ietf.utils.decorators import ignore_view_kwargs
from ietf.utils.http import is_ajax
from ietf.utils.response import permission_denied


def lookup_community_list(request, email_or_name=None, acronym=None):
    """Finds a CommunityList for a person or group
    
    Instantiates an unsaved CommunityList if one is not found.
    
    If the person or group cannot be found and uniquely identified, raises an Http404 exception
    """
    assert email_or_name or acronym

    if acronym:
        group = get_object_or_404(Group, acronym=acronym)
        clist = CommunityList.objects.filter(group=group).first() or CommunityList(group=group)
    else:
        persons = lookup_persons(email_or_name)
        if len(persons) > 1:
            if hasattr(request.user, 'person') and request.user.person in persons:
                person = request.user.person
            else:
                raise Http404(f"Unable to identify the CommunityList for {email_or_name}")
        else:
            person = persons[0]
        clist = CommunityList.objects.filter(person=person).first() or CommunityList(person=person)
    return clist

def view_list(request, email_or_name=None):
    clist = lookup_community_list(request, email_or_name)  # may raise Http404
    docs = docs_tracked_by_community_list(clist)
    docs, meta = prepare_document_table(request, docs, request.GET)

    subscribed = request.user.is_authenticated and (EmailSubscription.objects.none() if clist.pk is None else EmailSubscription.objects.filter(community_list=clist, email__person__user=request.user))

    return render(request, 'community/view_list.html', {
        'clist': clist,
        'docs': docs,
        'meta': meta,
        'can_manage_list': can_manage_community_list(request.user, clist),
        'subscribed': subscribed,
        "email_or_name": email_or_name,
    })

@login_required
@ignore_view_kwargs("group_type")
def manage_list(request, email_or_name=None, acronym=None):
    # we need to be a bit careful because clist may not exist in the
    # database so we can't call related stuff on it yet
    clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404

    if not can_manage_community_list(request.user, clist):
        permission_denied(request, "You do not have permission to access this view")

    action = request.POST.get('action')

    if request.method == 'POST' and action == 'add_documents':
        add_doc_form = AddDocumentsForm(request.POST)
        if add_doc_form.is_valid():
            if clist.pk is None:
                clist.save()

            for d in add_doc_form.cleaned_data['documents']:
                if not d in clist.added_docs.all():
                    clist.added_docs.add(d)

            return HttpResponseRedirect("")
    else:
        add_doc_form = AddDocumentsForm()

    if request.method == 'POST' and action == 'remove_document':
        document_id = request.POST.get('document')
        if clist.pk is not None and document_id:
            document = get_object_or_404(clist.added_docs, id=document_id)
            clist.added_docs.remove(document)

            return HttpResponseRedirect("")

    rule_form = None
    if request.method == 'POST' and action == 'add_rule':
        rule_type_form = SearchRuleTypeForm(request.POST)
        if rule_type_form.is_valid():
            rule_type = rule_type_form.cleaned_data['rule_type']
            if rule_type:
                rule_form = SearchRuleForm(clist, rule_type, request.POST)
                if rule_form.is_valid():
                    if clist.pk is None:
                        clist.save()
    
                    rule = rule_form.save(commit=False)
                    rule.community_list = clist
                    rule.rule_type = rule_type
                    rule.save()
                    if rule.rule_type == "name_contains":
                        reset_name_contains_index_for_rule(rule)

                return HttpResponseRedirect("")
    else:
        rule_type_form = SearchRuleTypeForm()

    if request.method == 'POST' and action == 'remove_rule':
        rule_pk = request.POST.get('rule')
        if clist.pk is not None and rule_pk:
            rule = get_object_or_404(SearchRule, pk=rule_pk, community_list=clist)
            rule.delete()

        return HttpResponseRedirect("")

    rules = clist.searchrule_set.all() if clist.pk is not None else []
    for r in rules:
        r.matching_documents_count = docs_matching_community_list_rule(r).count()

    empty_rule_forms = { rule_type: SearchRuleForm(clist, rule_type) for rule_type, _ in SearchRule.RULE_TYPES }

    total_count = docs_tracked_by_community_list(clist).count()

    all_forms = [f for f in [rule_type_form, rule_form, add_doc_form, *empty_rule_forms.values()]
                 if f is not None]
    return render(request, 'community/manage_list.html', {
        'clist': clist,
        'rules': rules,
        'individually_added': clist.added_docs.all() if clist.pk is not None else [],
        'rule_type_form': rule_type_form,
        'rule_form': rule_form,
        'empty_rule_forms': empty_rule_forms,
        'total_count': total_count,
        'add_doc_form': add_doc_form,
        'all_forms': all_forms,
    })


@login_required
def track_document(request, name, email_or_name=None, acronym=None):
    doc = get_object_or_404(Document, name=name)

    if request.method == "POST":
        clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404
        if not can_manage_community_list(request.user, clist):
            permission_denied(request, "You do not have permission to access this view")

        if clist.pk is None:
            clist.save()

        if not doc in clist.added_docs.all():
            clist.added_docs.add(doc)

        if is_ajax(request):
            return HttpResponse(json.dumps({ 'success': True }), content_type='application/json')
        else:
            return HttpResponseRedirect(clist.get_absolute_url())

    return render(request, "community/track_document.html", {
        "name": doc.name,
    })

@login_required
def untrack_document(request, name, email_or_name=None, acronym=None):
    doc = get_object_or_404(Document, name=name)
    clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404
    if not can_manage_community_list(request.user, clist):
        permission_denied(request, "You do not have permission to access this view")

    if request.method == "POST":
        if clist.pk is not None:
            clist.added_docs.remove(doc)

        if is_ajax(request):
            return HttpResponse(json.dumps({ 'success': True }), content_type='application/json')
        else:
            return HttpResponseRedirect(clist.get_absolute_url())

    return render(request, "community/untrack_document.html", {
        "name": doc.name,
    })


@ignore_view_kwargs("group_type")
def export_to_csv(request, email_or_name=None, acronym=None):
    clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404
    response = HttpResponse(content_type='text/csv')

    if clist.group:
        filename = "%s-draft-list.csv" % clist.group.acronym
    else:
        filename = "draft-list.csv"

    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    writer = csv.writer(response, dialect=csv.excel, delimiter=str(','))

    header = [
        "Name",
        "Title",
        "Date of latest revision",
        "Status in the IETF process",
        "Associated group",
        "Associated AD",
        "Date of latest change",
    ]
    writer.writerow(header)

    docs = docs_tracked_by_community_list(clist).select_related('type', 'group', 'ad')
    for doc in docs.prefetch_related("states", "tags"):
        row = []
        row.append(doc.name)
        row.append(doc.title)
        e = doc.latest_event(type='new_revision')
        row.append(e.time.strftime("%Y-%m-%d") if e else "")
        row.append(strip_tags(doc.friendly_state()))
        row.append(doc.group.acronym if doc.group else "")
        row.append(str(doc.ad) if doc.ad else "")
        e = doc.latest_event()
        row.append(e.time.strftime("%Y-%m-%d") if e else "")
        writer.writerow(row)

    return response

@ignore_view_kwargs("group_type")
def feed(request, email_or_name=None, acronym=None):
    clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404
    significant = request.GET.get('significant', '') == '1'

    documents = docs_tracked_by_community_list(clist).values_list('pk', flat=True)
    since = timezone.now() - datetime.timedelta(days=14)

    events = DocEvent.objects.filter(
        doc__id__in=documents,
        time__gte=since,
    ).distinct().order_by('-time', '-id').select_related("doc")

    if significant:
        events = events.filter(type="changed_state", statedocevent__state__in=list(states_of_significant_change()))

    host = request.get_host()
    feed_url = 'https://%s%s' % (host, request.get_full_path())
    feed_id = uuid.uuid5(uuid.NAMESPACE_URL, str(feed_url))
    title = '%s RSS Feed' % clist.long_name()
    if significant:
        subtitle = 'Significant document changes'
    else:
        subtitle = 'Document changes'

    return render(request, 'community/atom.xml', {
        'clist': clist,
        'entries': events[:50],
        'title': title,
        'subtitle': subtitle,
        'id': feed_id.urn,
        'updated': timezone.now(),
    }, content_type='text/xml')


@login_required
@ignore_view_kwargs("group_type")
def subscription(request, email_or_name=None, acronym=None):
    clist = lookup_community_list(request, email_or_name, acronym)  # may raise Http404
    if clist.pk is None:
        raise Http404

    person = request.user.person

    existing_subscriptions = EmailSubscription.objects.filter(community_list=clist, email__person=person)

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "subscribe":
            form = SubscriptionForm(person, clist, request.POST)
            if form.is_valid():
                subscription = form.save(commit=False)
                subscription.community_list = clist
                subscription.save()

                return HttpResponseRedirect("")

        elif action == "unsubscribe":
            existing_subscriptions.filter(pk=request.POST.get("subscription_id")).delete()

            return HttpResponseRedirect("")
    else:
        form = SubscriptionForm(person, clist)

    return render(request, 'community/subscription.html', {
        'clist': clist,
        'form': form,
        'existing_subscriptions': existing_subscriptions,
    })
