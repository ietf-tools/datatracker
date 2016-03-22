import csv
import uuid
import datetime
import json

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils.html import strip_tags

from ietf.community.models import SearchRule, EmailSubscription
from ietf.community.forms import SearchRuleTypeForm, SearchRuleForm, AddDocumentsForm, SubscriptionForm
from ietf.community.utils import lookup_community_list, can_manage_community_list
from ietf.community.utils import docs_tracked_by_community_list, docs_matching_community_list_rule
from ietf.community.utils import states_of_significant_change, reset_name_contains_index_for_rule
from ietf.doc.models import DocEvent, Document
from ietf.doc.utils_search import prepare_document_table

def view_list(request, username=None):
    clist = lookup_community_list(username)

    docs = docs_tracked_by_community_list(clist)
    docs, meta = prepare_document_table(request, docs, request.GET)

    subscribed = request.user.is_authenticated() and EmailSubscription.objects.filter(community_list=clist, email__person__user=request.user)

    return render(request, 'community/view_list.html', {
        'clist': clist,
        'docs': docs,
        'meta': meta,
        'can_manage_list': can_manage_community_list(request.user, clist),
        'subscribed': subscribed,
    })

@login_required
def manage_list(request, username=None, acronym=None, group_type=None):
    # we need to be a bit careful because clist may not exist in the
    # database so we can't call related stuff on it yet
    clist = lookup_community_list(username, acronym)

    if not can_manage_community_list(request.user, clist):
        return HttpResponseForbidden("You do not have permission to access this view")

    action = request.POST.get('action')

    if request.method == 'POST' and action == 'add_documents':
        add_doc_form = AddDocumentsForm(request.POST)
        if add_doc_form.is_valid():
            if clist.pk is None:
                clist.save()

            for d in add_doc_form.cleaned_data['documents']:
                clist.added_docs.add(d)

            return HttpResponseRedirect("")
    else:
        add_doc_form = AddDocumentsForm()

    if request.method == 'POST' and action == 'remove_document':
        document_pk = request.POST.get('document')
        if clist.pk is not None and document_pk:
            document = get_object_or_404(clist.added_docs, pk=document_pk)
            clist.added_docs.remove(document)

            return HttpResponseRedirect("")

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
        rule_form = None

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

    return render(request, 'community/manage_list.html', {
        'clist': clist,
        'rules': rules,
        'individually_added': clist.added_docs.all() if clist.pk is not None else [],
        'rule_type_form': rule_type_form,
        'rule_form': rule_form,
        'empty_rule_forms': empty_rule_forms,
        'total_count': total_count,
        'add_doc_form': add_doc_form,
    })


@login_required
def track_document(request, name, username=None, acronym=None):
    doc = get_object_or_404(Document, docalias__name=name)

    if request.method == "POST":
        clist = lookup_community_list(username, acronym)
        if not can_manage_community_list(request.user, clist):
            return HttpResponseForbidden("You do not have permission to access this view")

        if clist.pk is None:
            clist.save()

        clist.added_docs.add(doc)

        if request.is_ajax():
            return HttpResponse(json.dumps({ 'success': True }), content_type='text/plain')
        else:
            return HttpResponseRedirect(clist.get_absolute_url())

    return render(request, "community/track_document.html", {
        "name": doc.name,
    })

@login_required
def untrack_document(request, name, username=None, acronym=None):
    doc = get_object_or_404(Document, docalias__name=name)
    clist = lookup_community_list(username, acronym)
    if not can_manage_community_list(request.user, clist):
        return HttpResponseForbidden("You do not have permission to access this view")

    if request.method == "POST":
        if clist.pk is not None:
            clist.added_docs.remove(doc)

        if request.is_ajax():
            return HttpResponse(json.dumps({ 'success': True }), content_type='text/plain')
        else:
            return HttpResponseRedirect(clist.get_absolute_url())

    return render(request, "community/untrack_document.html", {
        "name": doc.name,
    })


def export_to_csv(request, username=None, acronym=None, group_type=None):
    clist = lookup_community_list(username, acronym)

    response = HttpResponse(content_type='text/csv')

    if clist.group:
        filename = "%s-draft-list.csv" % clist.group.acronym
    else:
        filename = "draft-list.csv"

    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    writer = csv.writer(response, dialect=csv.excel, delimiter=',')

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
        row.append(unicode(doc.ad) if doc.ad else "")
        e = doc.latest_event()
        row.append(e.time.strftime("%Y-%m-%d") if e else "")
        writer.writerow([v.encode("utf-8") for v in row])

    return response

def feed(request, username=None, acronym=None, group_type=None):
    clist = lookup_community_list(username, acronym)

    significant = request.GET.get('significant', '') == '1'

    documents = docs_tracked_by_community_list(clist).values_list('pk', flat=True)
    since = datetime.datetime.now() - datetime.timedelta(days=14)

    events = DocEvent.objects.filter(
        doc__in=documents,
        time__gte=since,
    ).distinct().order_by('-time', '-id').select_related("doc")

    if significant:
        events = events.filter(type="changed_state", statedocevent__state__in=list(states_of_significant_change()))

    host = request.get_host()
    feed_url = 'https://%s%s' % (host, request.get_full_path())
    feed_id = uuid.uuid5(uuid.NAMESPACE_URL, feed_url.encode('utf-8'))
    title = u'%s RSS Feed' % clist.long_name()
    if significant:
        subtitle = 'Significant document changes'
    else:
        subtitle = 'Document changes'

    return render(request, 'community/atom.xml', {
        'clist': clist,
        'entries': events[:50],
        'title': title,
        'subtitle': subtitle,
        'id': feed_id.get_urn(),
        'updated': datetime.datetime.now(),
    }, content_type='text/xml')


@login_required
def subscription(request, username=None, acronym=None, group_type=None):
    clist = lookup_community_list(username, acronym)
    if clist.pk is None:
        raise Http404

    existing_subscriptions = EmailSubscription.objects.filter(community_list=clist, email__person__user=request.user)

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "subscribe":
            form = SubscriptionForm(request.user, clist, request.POST)
            if form.is_valid():
                subscription = form.save(commit=False)
                subscription.community_list = clist
                subscription.save()

                return HttpResponseRedirect("")

        elif action == "unsubscribe":
            existing_subscriptions.filter(pk=request.POST.get("subscription_id")).delete()

            return HttpResponseRedirect("")
    else:
        form = SubscriptionForm(request.user, clist)

    return render(request, 'community/subscription.html', {
        'clist': clist,
        'form': form,
        'existing_subscriptions': existing_subscriptions,
    })
