import csv
import uuid
import datetime
import hashlib

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.models import User
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils import simplejson
from django.utils.http import urlquote

from ietf.community.models import CommunityList, Rule, EmailSubscription, ListNotification
from ietf.community.forms import RuleForm, DisplayForm, SubscribeForm, UnSubscribeForm
from redesign.group.models import Group
from redesign.doc.models import Document, DocEvent


def _manage_list(request, clist):
    display_config = clist.get_display_config()
    if request.method == 'POST' and request.POST.get('save_rule', None):
        rule_form = RuleForm(request.POST, clist=clist)
        display_form = DisplayForm(instance=display_config)
        if rule_form.is_valid():
            rule_form.save()
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
    return render_to_response('community/manage_clist.html',
                              {'cl': clist,
                               'dc': display_config,
                               'display_form': display_form,
                               'rule_form': rule_form},
                              context_instance=RequestContext(request))


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


def add_document(request, document_name):
    if not request.user.is_authenticated():
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    doc = get_object_or_404(Document, name=document_name)
    clist = CommunityList.objects.get_or_create(user=request.user)[0]
    clist.update()
    return add_document_to_list(request, clist, doc)


def remove_document(request, list_id, document_name):
    clist = get_object_or_404(CommunityList, pk=list_id)
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    doc = get_object_or_404(Document, name=document_name)
    clist.added_ids.remove(doc)
    clist.update()
    return HttpResponseRedirect(clist.get_manage_url())


def add_document_to_list(request, clist, doc):
    if not clist.check_manager(request.user):
        path = urlquote(request.get_full_path())
        tup = settings.LOGIN_URL, REDIRECT_FIELD_NAME, path
        return HttpResponseRedirect('%s?%s=%s' % tup)
    clist.added_ids.add(doc)
    return HttpResponse(simplejson.dumps({'success': True}), mimetype='text/plain')


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
    return render_to_response('community/public/view_list.html',
                              {'cl': clist,
                               'dc': display_config,
                              },
                              context_instance=RequestContext(request))


def view_personal_list(request, secret):
    clist = get_object_or_404(CommunityList, secret=secret)
    return _view_list(request, clist)


def view_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    clist = get_object_or_404(CommunityList, group=group)
    return _view_list(request, clist)


def _atom_view(request, clist, significant=False):
    documents = [i['pk'] for i in clist.get_documents().values('pk')]
    notifications = DocEvent.objects.filter(doc__pk__in=documents)\
                                            .distinct()\
                                            .order_by('-time', '-id')
    if significant:
        notifications = notifications.filter(listnotification__significant=True)

    host = request.get_host()
    feed_url = 'http://%s%s' % (host, request.get_full_path())
    feed_id = uuid.uuid5(uuid.NAMESPACE_URL, feed_url.encode('utf-8'))
    title = '%s RSS Feed' % clist.long_name()
    if significant:
        subtitle = 'Document significant changes'
    else:
        subtitle = 'Document changes'

    return render_to_response('community/public/atom.xml',
                              {'cl': clist,
                               'entries': notifications[:20],
                               'title': title,
                               'subtitle': subtitle,
                               'id': feed_id.get_urn(),
                               'updated': datetime.datetime.today(),
                              },
                              mimetype='text/xml',
                              context_instance=RequestContext(request))


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
    response = HttpResponse(mimetype='text/csv')
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


def _subscribe_list(request, clist, significant):
    success = False
    if request.method == 'POST':
        form = SubscribeForm(data=request.POST, clist=clist, significant=significant)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = SubscribeForm(clist=clist, significant=significant)
    return render_to_response('community/public/subscribe.html',
                              {'cl': clist,
                               'form': form,
                               'success': success,
                              },
                              context_instance=RequestContext(request))


def _unsubscribe_list(request, clist, significant):
    success = False
    if request.method == 'POST':
        form = UnSubscribeForm(data=request.POST, clist=clist, significant=significant)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = UnSubscribeForm(clist=clist, significant=significant)
    return render_to_response('community/public/unsubscribe.html',
                              {'cl': clist,
                               'form': form,
                               'success': success,
                               'significant': significant,
                              },
                              context_instance=RequestContext(request))


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
    return render_to_response('community/public/subscription_confirm.html',
                              {'cl': clist,
                               'significant': significant,
                              },
                              context_instance=RequestContext(request))


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
    return render_to_response('community/public/unsubscription_confirm.html',
                              {'cl': clist,
                               'significant': significant,
                              },
                              context_instance=RequestContext(request))


def confirm_significant_unsubscription(request, list_id, email, date, confirm_hash):
    return confirm_unsubscription(request, list_id, email, date, confirm_hash, significant=True)
