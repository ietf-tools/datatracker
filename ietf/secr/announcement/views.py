from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect

from ietf.group.models import Role
from ietf.message.models import AnnouncementFrom
from ietf.ietfauth.utils import has_role
from ietf.secr.announcement.forms import AnnounceForm
from ietf.secr.utils.decorators import check_for_cancel
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
        if has_role(user, "Secretariat"):
            return True
        
        for role in person.role_set.all():
            if AnnouncementFrom.objects.filter(name=role.name,group=role.group):
                return True

        if Role.objects.filter(name="chair",
                               group__acronym__startswith="nomcom",
                               group__state="active",
                               group__type="nomcom",
                               person=person):
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
        # recast as hidden form for next page of process
        form = AnnounceForm(request.POST, user=request.user, hidden=True)
        if form.data['to'] == 'Other...':
            to = form.data['to_custom']
        else:
            to = form.data['to']

        return render(request, 'announcement/confirm.html', {
            'message': form.data,
            'to': to,
            'form': form},
        )

    return render(request, 'announcement/main.html', { 'form': form} )

@login_required
@check_for_cancel('../')
def confirm(request):

    if not check_access(request.user):
        return HttpResponseForbidden('Restricted to: Secretariat, IAD, or chair of IETF, IAB, RSOC, RSE, IAOC, ISOC, NomCom.')

    if request.method == 'POST':
        form = AnnounceForm(request.POST, user=request.user)
        if request.method == 'POST':
            message = form.save(user=request.user,commit=True)
            extra = {'Reply-To': message.get('reply_to') }
            send_mail_text(None,
                           message.to,
                           message.frm,
                           message.subject,
                           message.body,
                           cc=message.cc,
                           bcc=message.bcc,
                           extra=extra,
                       )

            messages.success(request, 'The announcement was sent.')
            return redirect('ietf.secr.announcement.views.main')




