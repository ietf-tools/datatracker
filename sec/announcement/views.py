from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.ietfauth.decorators import group_required
from ietf.utils.mail import send_mail_text
from ietf.wgchairs.accounts import get_person_for_user
from ietf.group.models import Group
from sec.utils.group import current_nomcom
from sec.utils.decorators import check_for_cancel

from forms import *

# this seems to cause some kind of circular problem
# @check_for_cancel(reverse('home'))

@group_required('Area Director','Secretariat')
@check_for_cancel('../')
def main(request):

    form = AnnounceForm(request.POST or None)
    
    if form.is_valid():
        message = form.save(user=request.user,commit=True)
        send_mail_text(None, 
                       message.to,
                       message.frm,
                       message.subject,
                       message.body,
                       cc=message.cc,
                       bcc=message.bcc)
        
        messages.success(request, 'The announcement was sent.')
        url = reverse('home')
        return HttpResponseRedirect(url)
   
    return render_to_response('announcement/main.html', {
        'form': form},
        RequestContext(request, {}),
    )
