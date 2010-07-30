# Copyright The IETF Trust 2007, All Rights Reserved
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import simplejson

from ietf.liaisons.accounts import get_person_for_user
from ietf.liaisons.decorators import can_submit_liaison
from ietf.liaisons.forms import liaison_form_factory
from ietf.liaisons.models import SDOs
from ietf.liaisons.utils import IETFHM


@can_submit_liaison
def add_liaison(request):
    if request.method == 'POST':
        form = liaison_form_factory(request, data=request.POST.copy(),
                                    files = request.FILES)
        if form.is_valid():
            liaison = form.save()
            if request.POST.get('send', None):
                if not settings.DEBUG:
                    liaison.send_by_mail()
                else:
                    mail = liaison.send_by_email(fake=True)
                    return render_to_response('liaisons/liaison_mail_detail.html',
                                              {'mail': mail,
                                               'message': mail.message(),
                                               'liaison': liaison},
                                              context_instance=RequestContext(request))
            return HttpResponseRedirect(reverse('liaison_list'))
    else:
        form = liaison_form_factory(request)

    return render_to_response(
        'liaisons/liaisondetail_edit.html',
        {'form': form},
        context_instance=RequestContext(request),
    )


def get_info(request):
    person = get_person_for_user(request.user)

    to_entity_id = request.GET.get('to_entity_id', None)
    from_entity_id = request.GET.get('from_entity_id', None)

    result = {'poc': [], 'cc': [], 'needs_approval': False}

    to_error = 'Invalid TO entity id'
    if to_entity_id:
        to_entity = IETFHM.get_entity_by_key(to_entity_id)
        if to_entity:
            to_error = ''

    from_error = 'Invalid FROM entity id'
    if from_entity_id:
        from_entity = IETFHM.get_entity_by_key(from_entity_id)
        if from_entity:
            from_error = ''

    if to_error or from_error:
        result.update({'error': '\n'.join([to_error, from_error])})
    else:
        result.update({'error': False,
                       'cc': [i.email() for i in to_entity.get_cc(person=person)] +\
                             [i.email() for i in from_entity.get_from_cc(person=person)],
                       'poc': [i.email() for i in to_entity.get_poc()],
                       'needs_approval': from_entity.needs_approval(person=person)})
    json_result = simplejson.dumps(result)
    return HttpResponse(json_result, mimetype='text/javascript')
