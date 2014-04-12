from functools import wraps

from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404

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
    This decorator checks that the user making the request has access to the
    object being requested.  Expects one of the following four keyword
    arguments:

    acronym: a group acronym
    session_id: a session id (used for sessions of type other or plenary)
    meeting_id, slide_id
    """
    def wrapper(request, *args, **kwargs):
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

        login = request.user.person
        groups = [group]
        if group.parent:
            groups.append(group.parent)
        all_roles = Role.objects.filter(group__in=groups,name__in=('ad','chair','secr'))
        if login in [ r.person for r in all_roles ]:
            return func(request, *args, **kwargs)

        # if session is plenary allow ietf/iab chairs
        if session and get_timeslot(session).type.slug=='plenary':
            if login.role_set.filter(name='chair',group__acronym__in=('iesg','iab')):
                return func(request, *args, **kwargs)

        # if we get here access is denied
        return render_to_response('unauthorized.html',{
            'user_name':login,
            'group_name':group.acronym}
        )
    return wraps(func)(wrapper)

def sec_only(func):
    """
    This decorator checks that the user making the request is a secretariat user.
    (Based on the cusotm user_is_secretariat request attribute)
    """
    def wrapper(request, *args, **kwargs):
        # short circuit.  secretariat user has full access
        if request.user_is_secretariat:
            return func(request, *args, **kwargs)

        return render_to_response('unauthorized.html',{
            'user_name':request.user.person}
        )

    return wraps(func)(wrapper)
