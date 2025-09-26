from django import template
from ietf.person.models import Person


register = template.Library()

@register.filter
def abbr_status(value):
    """
    Converts RFC Status to a short abbreviation
    """
    d = {'Proposed Standard':'PS',
         'Draft Standard':'DS',
         'Standard':'S',
         'Historic':'H',
         'Informational':'I',
         'Experimental':'E',
         'Best Current Practice':'BCP',
         'Internet Standard':'IS'}

    return d.get(value,value)

@register.filter(name='display_duration')
def display_duration(value):
    """
    Maps a session requested duration from select index to 
    label."""
    if value in (None, ''):
        return 'unspecified'
    value = int(value)
    map = {0: 'None',
           1800: '30 Minutes',
           3600: '1 Hour',
           5400: '1.5 Hours',
           7200: '2 Hours',
           9000: '2.5 Hours',
           10800: '3 Hours',
           12600: '3.5 Hours',
           14400: '4 Hours'}
    if value in map:
        return map[value]
    else:
        return "%d Hours %d Minutes %d Seconds"%(value//3600,(value%3600)//60,value%60)

@register.filter
def is_ppt(value):
    '''
    Checks if the value ends in ppt or pptx
    '''
    if value.endswith('ppt') or value.endswith('pptx'):
        return True
    else:
        return False
        
@register.filter
def smart_login(user):
    '''
    Expects a Person object.  If person is a Secretariat returns "on behalf of the"
    '''
    if not isinstance (user, Person):
        return user
    if user.role_set.filter(name='secr',group__acronym='secretariat'):
        return '%s, on behalf of the' % user
    else:
        return '%s, a chair of the' % user
