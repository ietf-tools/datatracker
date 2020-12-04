# Copyright The IETF Trust 2013-2020, All Rights Reserved
from functools import wraps

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.http import urlquote

from ietf.ietfauth.utils import has_role
from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.models import Session
from ietf.secr.utils.meeting import get_timeslot
from ietf.utils.response import permission_denied

            
def check_for_cancel(redirect_url):
    """
    Decorator to make a view redirect to the given url if the reuqest is a POST which contains
    a submit=Cancel.
    """
    def decorator(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            if request.method == 'POST' and request.POST.get('submit',None) == 'Cancel':
                return HttpResponseRedirect(redirect_url)
            return func(request, *args, **kwargs)
        return inner
    return decorator

def check_permissions(func):
    """
    View decorator for checking that the user is logged in and has access to the
    object being requested.  Expects one of the following four keyword
    arguments:

    acronym: a group acronym
    session_id: a session id (used for sessions of type other or plenary)
    meeting_id, slide_id
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect('%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, urlquote(request.get_full_path())))
        
        session = None
        # short circuit.  secretariat user has full access
        if has_role(request.user,'Secretariat'):
            return func(request, *args, **kwargs)
        # get the parent group
        if 'acronym' in kwargs:
            acronym = kwargs['acronym']
            group = get_object_or_404(Group,acronym=acronym)
        elif 'session_id' in kwargs:
            session = get_object_or_404(Session, id=kwargs['session_id'])
            group = session.group
        elif 'slide_id' in kwargs:
            slide = get_object_or_404(Document, name=kwargs['slide_id'])
            session = slide.session_set.all()[0]
            group = session.group

        try:
            login = request.user.person
        except ObjectDoesNotExist:
            permission_denied(request, "User not authorized to access group: %s" % group.acronym)
            
        if login.role_set.filter(name__in=group.features.groupman_roles,group=group):
            return func(request, *args, **kwargs)
        elif group.parent and login.role_set.filter(name__in=group.parent.features.groupman_roles,group=group.parent):
            return func(request, *args, **kwargs)

        # if session is plenary allow ietf/iab chairs
        if session and get_timeslot(session).type.slug=='plenary':
            chair = login.role_set.filter(name='chair',group__acronym__in=('iesg','iab','ietf-trust','iaoc'))
            admdir = login.role_set.filter(name='admdir',group__acronym='ietf')
            if chair or admdir:
                return func(request, *args, **kwargs)

        # if we get here access is denied
        permission_denied(request, "User not authorized to access group: %s" % group.acronym)
        
    return wraps(func)(wrapper)

def sec_only(func):
    """
    This decorator checks that the user making the request is a secretariat user.
    """
    def wrapper(request, *args, **kwargs):
        # short circuit.  secretariat user has full access
        if has_role(request.user, "Secretariat"):
            return func(request, *args, **kwargs)

        return render(request, 'unauthorized.html',{ 'user_name':request.user.person } )

    return wraps(func)(wrapper)
