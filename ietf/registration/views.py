import datetime
import hashlib

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _

from ietf.registration.forms import (RegistrationForm, PasswordForm,
                                     RecoverPasswordForm)


def register_view(request):
    success = False
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = RegistrationForm()
    return render_to_response('registration/register.html',
                              {'form': form,
                               'success': success},
                              context_instance=RequestContext(request))


def confirm_register_view(request, username, date, realm, registration_hash):
    valid = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, date, username, realm)).hexdigest() == registration_hash
    if not valid:
        raise Http404
    request_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
    if datetime.date.today() > (request_date + datetime.timedelta(days=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK)):
        raise Http404
    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST, username=username)
        if form.is_valid():
            form.save()
            # TODO: Add the user in the htdigest file
            success = True
    else:
        form = PasswordForm(username=username)
    return render_to_response('registration/confirm_register.html',
                              {'form': form, 'email': username, 'success': success},
                              context_instance=RequestContext(request))


def password_recovery_view(request):
    success = False
    if request.method == 'POST':
        form = RecoverPasswordForm(request.POST)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = RecoverPasswordForm()
    return render_to_response('registration/password_recovery.html',
                              {'form': form,
                               'success': success},
                              context_instance=RequestContext(request))


def confirm_password_recovery(request, username, date, realm, recovery_hash):
    user = get_object_or_404(User, username=username)
    valid = hashlib.md5('%s%s%s%s%s' % (settings.SECRET_KEY, date, user.username, user.password, realm)).hexdigest() == recovery_hash
    if not valid:
        raise Http404
    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST, update_user=True, username=user.username)
        if form.is_valid():
            user = form.save()
            # TODO: Update the user in the htdigest file
            success = True
    else:
        form = PasswordForm(username=user.username)
    return render_to_response('registration/change_password.html',
                              {'form': form,
                               'success': success,
                               'username': user.username},
                              context_instance=RequestContext(request))


def ajax_check_username(request):
    username = request.GET.get('username', '')
    error = False
    if User.objects.filter(username=username).count():
        error = _('This email is already in use')
    return HttpResponse(simplejson.dumps({'error': error}), mimetype='text/plain')
