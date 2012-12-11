from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

from ietf.nomcom.forms import EditPublicKeyForm, NominateForm
from ietf.nomcom.models import NomCom


@login_required
def edit_publickey(request, year):
    nomcom = get_object_or_404(NomCom,
                              group__acronym__icontains=year,
                              group__state__slug='active')
    is_group_chair = nomcom.group.is_chair(request.user)
    if not is_group_chair:
        return HttpResponseForbidden("Must be group chair")

    message = ('warning', 'Previous data will remain encrypted with the old key')
    if request.method == 'POST':
        form = EditPublicKeyForm(request.POST,
                                 request.FILES,
                                 instance=nomcom,
                                 initial={'public_key': None})
        if form.is_valid():
            form.save()
            message = ('success', 'The public key has been changed')
    else:
        form = EditPublicKeyForm()

    return render_to_response('nomcom/edit_publickey.html',
                              {'form': form,
                               'group': nomcom.group,
                               'message': message}, RequestContext(request))


@login_required
def nominate(request, year):
    nomcom = get_object_or_404(NomCom,
                              group__acronym__icontains=year,
                              group__state__slug='active')
    message = None
    if request.method == 'POST':
        form = NominateForm(data=request.POST, nomcom=nomcom, user=request.user)
        if form.is_valid():
            form.save()
            message = ('success', 'The nomination has been successfully done')
    else:
        form = NominateForm(nomcom=nomcom, user=request.user)

    return render_to_response('nomcom/nominate.html',
                              {'form': form,
                               'message': message}, RequestContext(request))
