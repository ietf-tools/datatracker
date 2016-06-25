from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext

from ietf.group.models import Role
from ietf.ietfauth.utils import has_role
from ietf.secr.announcement.forms import AnnounceForm
from ietf.secr.utils.decorators import check_for_cancel, clear_non_auth
from ietf.utils.mail import send_mail_text

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def check_access(user):
    '''
    This function takes a Django User object and returns true if the user has access to
    the Announcement app.
    '''
    if hasattr(user, "person"):
        person = user.person
        groups_with_access = ("iab", "isoc", "isocbot", "rsoc", "ietf", "iaoc", "rse", "mentor","ietf-trust")
        if Role.objects.filter(person=person,
                               group__acronym__in=groups_with_access,
                               name="chair") or has_role(user, ["Secretariat","IAD"]):
            return True
        if Role.objects.filter(name="chair",
                               group__acronym__startswith="nomcom",
                               group__state="active",
                               group__type="nomcom",
                               person=person):
            return True
        if Role.objects.filter(person=person,
                               group__acronym='iab',
                               name='execdir'):
            return True
        if Role.objects.filter(person=person,
                               group__acronym='isoc',
                               name='ceo'):
            return True

    return False

# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
# this seems to cause some kind of circular problem
# @check_for_cancel(reverse('home'))
@login_required
@check_for_cancel('../')
def main(request):
    '''
    Main view for Announcement tool.  Authrozied users can fill out email details: header, body, etc
    and send.
    '''
    if not check_access(request.user):
        return HttpResponseForbidden('Restricted to: Secretariat, IAD, or chair of IETF, IAB, RSOC, RSE, IAOC, ISOC, NomCom.')

    form = AnnounceForm(request.POST or None,user=request.user)

    if form.is_valid():
        # nomcom is a ModelChoice, store pk, not Group object
        data = form.cleaned_data
        if data['nomcom']:
            data['nomcom'] = data['nomcom'].pk
        request.session['data'] = data

        return redirect('announcement_confirm')

    return render_to_response('announcement/main.html', {
        'form': form},
        RequestContext(request, {}),
    )

@login_required
@check_for_cancel('../')
def confirm(request):

    if request.session.get('data',None):
        data = request.session['data']
    else:
        messages.error(request, 'No session data.  Your session may have expired or cookies are disallowed.')
        return redirect('announcement')

    if request.method == 'POST':
        form = AnnounceForm(data, user=request.user)
        message = form.save(user=request.user,commit=True)
        extra = {'Reply-To':message.reply_to}
        send_mail_text(None,
                       message.to,
                       message.frm,
                       message.subject,
                       message.body,
                       cc=message.cc,
                       bcc=message.bcc,
                       extra=extra)

        # clear session
        clear_non_auth(request.session)

        messages.success(request, 'The announcement was sent.')
        return redirect('announcement')

    if data['to'] == 'Other...':
        to = ','.join(data['to_custom'])
    else:
        to = data['to']

    return render_to_response('announcement/confirm.html', {
        'message': data,
        'to': to},
        RequestContext(request, {}),
    )
