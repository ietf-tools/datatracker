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
        # short circuit.  secretariat user has full access
        if has_role(request.user,'Secretariat'):
            return func(request, *args, **kwargs)
        #assert False, kwargs
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
            '''
        elif 'meeting_id' in kwargs:
            meeting = Meeting.objects.get(id=kwargs['meeting_id'])
            group_id = meeting.group
        elif 'slide_id' in kwargs:
            slide = InterimFile.objects.get(id=kwargs['slide_id'])
            group_id = slide.meeting.group_acronym_id
        
            
        if has_role(request.user,'Area Director'):
            ad = AreaDirector.objects.get(person=request.person)
            ags = AreaGroup.objects.filter(area=ad.area)
            if ags.filter(group=group_id):
                return func(request, *args, **kwargs)
        else:
            if ( WGChair.objects.filter(group_acronym=group_id,person=request.person) or
            WGSecretary.objects.filter(group_acronym=group_id,person=request.person) or
            IRTFChair.objects.filter(irtf=group_id,person=request.person)):
                return func(request, *args, **kwargs)
        
        if request.user_is_ietf_iab_chair and group_id in ('-1','-2'):
            return func(request, *args, **kwargs)
        '''
        
        login = request.user.get_profile()
        all_roles = chain(
            group.role_set.filter(name__in=('chair','secr')),
            group.parent.role_set.filter(name__in=('ad','chair')))
        if login in [ r.person for r in all_roles ]:
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
