from functools import wraps

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.utils.http import urlquote

from ietf.ietfauth.utils import has_role
from ietf.doc.models import Document
from ietf.group.models import Group, Role
from ietf.meeting.models import Session
from ietf.secr.utils.meeting import get_timeslot

def clear_non_auth(session):
    """
    Clears non authentication related keys from the session object
    """
    for key in session.keys():
        if not key.startswith('_auth'):
            del session[key]
            
def check_for_cancel(redirect_url):
    """
    Decorator to make a view redirect to the given url if the reuqest is a POST which contains
    a submit=Cancel.
    """
    def decorator(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            if request.method == 'POST' and request.POST.get('submit',None) == 'Cancel':
                clear_non_auth(request.session)
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
        if not request.user.is_authenticated():
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
            return HttpResponseForbidden("User not authorized to access group: %s" % group.acronym)
            
        groups = [group]
        if group.parent:
            groups.append(group.parent)
        all_roles = Role.objects.filter(group__in=groups,name__in=('ad','chair','secr'))
        if login in [ r.person for r in all_roles ]:
            return func(request, *args, **kwargs)

        # if session is plenary allow ietf/iab chairs
        if session and get_timeslot(session).type.slug=='plenary':
            chair = login.role_set.filter(name='chair',group__acronym__in=('iesg','iab','ietf-trust','iaoc'))
            admdir = login.role_set.filter(name='admdir',group__acronym='ietf')
            if chair or admdir:
                return func(request, *args, **kwargs)

        # if we get here access is denied
        return HttpResponseForbidden("User not authorized to access group: %s" % group.acronym)
        
    return wraps(func)(wrapper)

def sec_only(func):
    """
    This decorator checks that the user making the request is a secretariat user.
    """
    def wrapper(request, *args, **kwargs):
        # short circuit.  secretariat user has full access
        if has_role(request.user, "Secretariat"):
            return func(request, *args, **kwargs)

        return render_to_response('unauthorized.html',{
            'user_name':request.user.person}
        )

    return wraps(func)(wrapper)
