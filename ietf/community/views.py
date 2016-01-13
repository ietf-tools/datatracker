import csv
import uuid
import datetime
import hashlib
import json

from django.db import IntegrityError
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponse, HttpResponseForbidden, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.http import urlquote
from django.contrib.auth.decorators import login_required

from ietf.community.models import CommunityList, Rule, EmailSubscription
from ietf.community.forms import RuleForm, DisplayForm, SubscribeForm, UnSubscribeForm
from ietf.group.models import Group
from ietf.doc.models import DocEvent, Document


def _manage_list(request, clist):
    display_config = clist.get_display_config()
    if request.method == 'POST' and request.POST.get('save_rule', None):
        rule_form = RuleForm(request.POST, clist=clist)
        display_form = DisplayForm(instance=display_config)
        if rule_form.is_valid():
            try:
                rule_form.save()
            except IntegrityError:
                pass;
            rule_form = RuleForm(clist=clist)
            display_form = DisplayForm(instance=display_config)
    elif request.method == 'POST' and request.POST.get('save_display', None):
        display_form = DisplayForm(request.POST, instance=display_config)
        rule_form = RuleForm(clist=clist)
        if display_form.is_valid():
            display_form.save()
            rule_form = RuleForm(clist=clist)
            display_form = DisplayForm(instance=display_config)
    else:
        rule_form = RuleForm(clist=clist)
        display_form = DisplayForm(instance=display_config)
    clist = CommunityList.objects.get(id=clist.id)
    return render(request, 'community/manage_clist.html',
                              {'cl': clist,
                               'dc': display_config,
                               'display_form': display_form,
                               'rule_form': rule_form})


def manage_personal_list(request):
    user = request.user
    if not user.is_authenticated():
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    clist = CommunityList.objects.get_or_create(user=request.user)[0]
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    return _manage_list(request, clist)


def manage_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    if group.type.slug not in ('area', 'wg'):
        raise Http404
    clist = CommunityList.objects.get_or_create(group=group)[0]
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    return _manage_list(request, clist)

@login_required
def track_document(request, name):
    doc = get_object_or_404(Document, docalias__name=name)

    if request.method == "POST":
        clist = CommunityList.objects.get_or_create(user=request.user)[0]
        clist.added_ids.add(doc)
        if request.is_ajax():
            return HttpResponse(json.dumps({ 'success': True }), content_type='text/plain')
        else:
            return redirect("manage_personal_list")

    return render(request, "community/track_document.html", {
        "name": doc.name,
    })

@login_required
def untrack_document(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    clist = get_object_or_404(CommunityList, user=request.user)

    if request.method == "POST":
        clist = CommunityList.objects.get_or_create(user=request.user)[0]
        clist.added_ids.remove(doc)
        if request.is_ajax():
            return HttpResponse(json.dumps({ 'success': True }), content_type='text/plain')
        else:
            return redirect("manage_personal_list")

    return render(request, "community/untrack_document.html", {
        "name": doc.name,
    })

@login_required
def remove_document(request, list_id, name):
    clist = get_object_or_404(CommunityList, pk=list_id)
    if not clist.check_manager(request.user):
        return HttpResponseForbidden("You do not have permission to access this view")

    doc = get_object_or_404(Document, docalias__name=name)
    clist.added_ids.remove(doc)

    return HttpResponseRedirect(clist.get_manage_url())


def remove_rule(request, list_id, rule_id):
    clist = get_object_or_404(CommunityList, pk=list_id)
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    rule = get_object_or_404(Rule, pk=rule_id)
    rule.delete()
    return HttpResponseRedirect(clist.get_manage_url())


def _view_list(request, clist):
    display_config = clist.get_display_config()
    return render(request, 'community/public/view_list.html',
                              {'cl': clist,
                               'dc': display_config,
                              })


def view_personal_list(request, secret):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _view_list(request, clist)


def view_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _view_list(request, clist)


def _atom_view(request, clist, significant=False):
    documents = [i['pk'] for i in clist.get_documents().values('pk')]
    startDate = datetime.datetime.now() - datetime.timedelta(days=14)

    notifications = DocEvent.objects.filter(doc__pk__in=documents, time__gte=startDate)\
                                            .distinct()\
                                            .order_by('-time', '-id')
    if significant:
        notifications = notifications.filter(listnotification__significant=True)

    host = request.get_host()
    feed_url = 'https://%s%s' % (host, request.get_full_path())
    feed_id = uuid.uuid5(uuid.NAMESPACE_URL, feed_url.encode('utf-8'))
    title = '%s RSS Feed' % clist.long_name()
    if significant:
        subtitle = 'Document significant changes'
    else:
        subtitle = 'Document changes'

    return render(request, 'community/public/atom.xml',
                              {'cl': clist,
                               'entries': notifications,
                               'title': title,
                               'subtitle': subtitle,
                               'id': feed_id.get_urn(),
                               'updated': datetime.datetime.today(),
                              },
                              content_type='text/xml')


def changes_personal_list(request, secret):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _atom_view(request, clist)


def changes_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _atom_view(request, clist)


def significant_personal_list(request, secret):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _atom_view(request, clist, significant=True)


def significant_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _atom_view(request, clist, significant=True)


def _csv_list(request, clist):
    display_config = clist.get_display_config()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=draft-list.csv'

    writer = csv.writer(response, dialect=csv.excel, delimiter=',')
    header = []
    fields = display_config.get_all_fields()
    for field in fields:
        header.append(field.description)
    writer.writerow(header)

    for doc in clist.get_documents():
        row = []
        for field in fields:
            row.append(field().get_value(doc, raw=True))
        writer.writerow(row)
    return response


def csv_personal_list(request):
    user = request.user
    if not user.is_authenticated():
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    clist = CommunityList.objects.get_or_create(user=user)[0]
    if not clist.check_manager(user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    return _csv_list(request, clist)


def csv_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    if group.type.slug not in ('area', 'wg'):
        raise Http404
    clist = CommunityList.objects.get_or_create(group=group)[0]
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    return _csv_list(request, clist)

def view_csv_personal_list(request, secret):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _csv_list(request, clist)

def _subscribe_list(request, clist, significant):
    success = False
    if request.method == 'POST':
        form = SubscribeForm(data=request.POST, clist=clist, significant=significant)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = SubscribeForm(clist=clist, significant=significant)
    return render(request, 'community/public/subscribe.html',
                              {'cl': clist,
                               'form': form,
                               'success': success,
                              })


def _unsubscribe_list(request, clist, significant):
    success = False
    if request.method == 'POST':
        form = UnSubscribeForm(data=request.POST, clist=clist, significant=significant)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = UnSubscribeForm(clist=clist, significant=significant)
    return render(request, 'community/public/unsubscribe.html',
                              {'cl': clist,
                               'form': form,
                               'success': success,
                               'significant': significant,
                              })


def subscribe_personal_list(request, secret, significant=False):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _subscribe_list(request, clist, significant=significant)


def subscribe_group_list(request, acronym, significant=False):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _subscribe_list(request, clist, significant=significant)


def unsubscribe_personal_list(request, secret, significant=False):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _unsubscribe_list(request, clist, significant=significant)


def unsubscribe_group_list(request, acronym, significant=False):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _unsubscribe_list(request, clist, significant=significant)


def confirm_subscription(request, list_id, email, date, confirm_hash, significant=False):
    clist = get_object_or_404(CommunityList, pk=list_id)
    valid = hashlib.md5('%s%s%s%s%s' % (settings.SECRET_KEY, date, email, 'subscribe', significant)).hexdigest() == confirm_hash
    if not valid:
        raise Http404
    (subscription, created) = EmailSubscription.objects.get_or_create(
        community_list=clist,
        email=email,
        significant=significant)
    return render(request, 'community/public/subscription_confirm.html',
                              {'cl': clist,
                               'significant': significant,
                              })


def confirm_significant_subscription(request, list_id, email, date, confirm_hash):
    return confirm_subscription(request, list_id, email, date, confirm_hash, significant=True)


def confirm_unsubscription(request, list_id, email, date, confirm_hash, significant=False):
    clist = get_object_or_404(CommunityList, pk=list_id)
    valid = hashlib.md5('%s%s%s%s%s' % (settings.SECRET_KEY, date, email, 'unsubscribe', significant)).hexdigest() == confirm_hash
    if not valid:
        raise Http404
    EmailSubscription.objects.filter(
        community_list=clist,
        email=email,
        significant=significant).delete()
    return render(request, 'community/public/unsubscription_confirm.html',
                              {'cl': clist,
                               'significant': significant,
                              })


def confirm_significant_unsubscription(request, list_id, email, date, confirm_hash):
    return confirm_unsubscription(request, list_id, email, date, confirm_hash, significant=True)
