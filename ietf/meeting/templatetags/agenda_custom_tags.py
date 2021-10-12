# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import template
from django.urls import reverse

from ietf.utils.text import xslugify

register = template.Library()



# returns the a dictioary's value from it's key.
@register.filter(name='lookup')
def lookup(dict, index):
    if index in dict:
        return dict[index]
    return ''

# returns the length of the value of a dict.
# We are doing this to how long the title for the calendar should be. (this should return the number of time slots)
@register.filter(name='colWidth')
def get_col_width(dict, index):
    if index in dict:
        return len(dict[index])
    return 0

# Replaces characters that are not acceptable html ID's
@register.filter(name='to_acceptable_id')
def to_acceptable_id(inp):
    # see http://api.jquery.com/category/selectors/?rdfrom=http%3A%2F%2Fdocs.jquery.com%2Fmw%2Findex.php%3Ftitle%3DSelectors%26redirect%3Dno
    # for more information.
    invalid = ["!","\"", "#","$","%","&","'","(",")","*","+",",",".","/",":",";","<","=",">","?","@","[","\\","]","^","`","{","|","}","~"," "]
    out = str(inp)
    for i in invalid:
        out = out.replace(i,'_')
    return out


@register.filter(name='durationFormat')
def durationFormat(inp):
    return "%.1f" % (float(inp)/3600)

# from:
#    http://www.sprklab.com/notes/13-passing-arguments-to-functions-in-django-template
#
@register.filter(name="call")
def callMethod(obj, methodName):
    method = getattr(obj, methodName)

    if "__callArg" in obj.__dict__:
        ret = method(*obj.__callArg)
        del obj.__callArg
        return ret
    return method()

@register.filter(name="args")
def args(obj, arg):
    if "__callArg" not in obj.__dict__:
        obj.__callArg = []

    obj.__callArg += [arg]
    return obj

@register.simple_tag(name='webcal_url', takes_context=True)
def webcal_url(context, viewname, *args, **kwargs):
    """webcal URL for a view"""
    return 'webcal://{}{}'.format(
        context.request.get_host(),
        reverse(viewname, args=args, kwargs=kwargs)
    )

@register.simple_tag
def assignment_display_name(assignment):
    """Get name for an assignment"""
    if assignment.session.type.slug == 'session' and assignment.session.historic_group:
        return assignment.session.historic_group.name
    return assignment.session.name or assignment.timeslot.name


class AnchorNode(template.Node):
    """Template node for a conditionally-included anchor

    If self.resolve_url() returns a URL, the contents of the nodelist will be rendered inside
    <a href="{{ self.resolve_url() }}"> ... </a>. If it returns None, the <a> will be omitted.
    The contents will be rendered in either case.
    """
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def resolve_url(self, context):
        raise NotImplementedError('Subclasses must define this method')

    def render(self, context):
        url = self.resolve_url(context)
        if url:
            return '<a href="{}">{}</a>'.format(url, self.nodelist.render(context))
        else:
            return self.nodelist.render(context)


class AgendaAnchorNode(AnchorNode):
    """Template node for the agenda_anchor tag"""
    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = template.Variable(session)

    def resolve_url(self, context):
        sess = self.session.resolve(context)
        agenda = sess.agenda()
        if agenda:
            return agenda.get_href()
        return None


@register.tag
def agenda_anchor(parser, token):
    """Block tag that wraps its content in a link to the session agenda, if any"""
    try:
        tag_name, sess_var = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError('agenda_anchor requires a single argument')
    nodelist = parser.parse(('end_agenda_anchor',))
    parser.delete_first_token()  # delete the end tag
    return AgendaAnchorNode(sess_var, nodelist)


class LocationAnchorNode(AnchorNode):
    """Template node for the location_anchor tag"""
    def __init__(self, timeslot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeslot = template.Variable(timeslot)

    def resolve_url(self, context):
        ts = self.timeslot.resolve(context)
        if ts.show_location and ts.location:
            return ts.location.floorplan_url()
        return None

@register.tag
def location_anchor(parser, token):
    """Block tag that wraps its content in a link to the timeslot location

    If the timeslot has no location information or is marked with show_location=False,
    the anchor tag is omitted.
    """
    try:
        tag_name, ts_var = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError('location_anchor requires a single argument')
    nodelist = parser.parse(('end_location_anchor',))
    parser.delete_first_token()  # delete the end tag
    return LocationAnchorNode(ts_var, nodelist)
