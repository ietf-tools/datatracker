from django import template

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
         'Experimental':'E'}

    return d.get(value,value)

@register.filter(name='display_duration')
def display_duration(value):
    """
    Maps a session requested duration from select index to 
    label."""
    map = {'3600':'1 Hour',
           '5400':'1.5 Hours',
           '7200':'2 Hours',
           '9000':'2.5 Hours'}
    return map[value]

@register.filter
def is_ppt(value):
    '''
    Checks if the value ends in ppt or pptx
    '''
    if value.endswith('ppt') or value.endswith('pptx'):
        return True
    else:
        return False