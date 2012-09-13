from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.ietfauth.decorators import has_role
from ietf.utils.mail import send_mail_text
from ietf.wgchairs.accounts import get_person_for_user
from ietf.group.models import Group
from sec.utils.group import current_nomcom
from sec.utils.decorators import check_for_cancel

from forms import *

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def check_access(user):
    '''
    This function takes a Django User object and returns true if the user has access to the
    Announcement app.  Accepted roles are:
    Secretariat, IAD, IAB Chair, IETF Chair, RSOC Chair, IAOC Chair, NomCom Chair, RSE Chair
    '''
    person = user.get_profile()
    groups_with_access = ("iab", "rsoc", "ietf", "iaoc", "rse")
    if Role.objects.filter(person=person,
                           group__acronym__in=groups_with_access,
                           name="chair") or has_role(user, ["Secretariat","IAD"]):
        return True
    if Role.objects.filter(name="chair",
                           group__acronym__startswith="nomcom",
                           group__state="active",
                           group__type="ietf",
                           person=person):
        return True
    
    return False
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
# this seems to cause some kind of circular problem
# @check_for_cancel(reverse('home'))
@check_for_cancel('../')
def main(request):
    '''
    Main view for Announcement tool.  Authrozied users can fill out email details: header, body, etc
    and send.
    '''
    if not check_access(request.user):
        return HttpResponseForbidden('Restricted to: Secretariat, IAD, or chair of IETF, IAB, RSOC, RSE, IAOC, NomCom.')
    
    form = AnnounceForm(request.POST or None,user=request.user)
    
    if form.is_valid():
        request.session['data'] = form.cleaned_data
        
        url = reverse('announcement_confirm')
        return HttpResponseRedirect(url)

    return render_to_response('announcement/main.html', {
        'form': form},
        RequestContext(request, {}),
    )

@check_for_cancel('../')
def confirm(request):
    
    # testing
    #assert False, (request.session.get_expiry_age(),request.session.get_expiry_date())
    
    if request.method == 'POST':
        form = AnnounceForm(request.session['data'],user=request.user)
        message = form.save(user=request.user,commit=True)
        send_mail_text(None, 
                       message.to,
                       message.frm,
                       message.subject,
                       message.body,
                       cc=message.cc,
                       bcc=message.bcc)

        # clear session
        request.session.clear()
        
        messages.success(request, 'The announcement was sent.')
        url = reverse('announcement')
        return HttpResponseRedirect(url)
    
    if request.session.get('data',None):
        data = request.session['data']
    else:
        messages.error(request, 'No session data.  Your session may have expired or cookies are disallowed.')
        redirect_url = reverse('announcement')
        return HttpResponseRedirect(redirect_url)
    
    if data['to'] == 'Other...':
        to = ','.join(data['to_custom'])
    else:
        to = data['to']
        
    return render_to_response('announcement/confirm.html', {
        'message': data,
        'to': to},
        RequestContext(request, {}),
    )