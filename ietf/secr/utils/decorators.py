from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from functools import wraps

from ietf.ietfauth.decorators import has_role
from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.models import Session

from itertools import chain

def check_for_cancel(redirect_url):
    """
    Decorator to make a view redirect to the given url if the reuqest is a POST which contains
    a submit=Cancel.
    """
    def decorator(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            if request.method == 'POST' and request.POST.get('submit',None) == 'Cancel':
                request.session.clear()
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
        
        login = request.user.get_profile()
        all_roles = chain(
            group.role_set.filter(name__in=('chair','secr')),
            group.parent.role_set.filter(name__in=('ad','chair')))
        if login in [ r.person for r in all_roles ]:
            return func(request, *args, **kwargs)
            
        # if session is plenary allow ietf/iab chairs
        if session and session.timeslot_set.filter(type__slug='plenary'):
            if login.role_set.filter(name='Chair',group__acronym__in=('iesg','iab')):
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
            'user_name':request.user.get_profile()}
        )

    return wraps(func)(wrapper)
