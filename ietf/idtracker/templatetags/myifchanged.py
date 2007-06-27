# Copyright The IETF Trust 2007, All Rights Reserved

"""A copy of the IfChanged standard node, updated with
SmileyChris's patch in http://code.djangoproject.com/ticket/4534
and with the context push removed."""


from django.template import Node, NodeList, resolve_variable
from django.template import VariableDoesNotExist, TemplateSyntaxError
from django.template import Library

register = Library()

class MyIfChangedNode(Node):
    def __init__(self, nodelist_true, nodelist_false, *varlist):
        self.nodelist_true, self.nodelist_false = nodelist_true, nodelist_false
        self._last_seen = None
        self._varlist = varlist

    def render(self, context):
        #if context.has_key('forloop') and context['forloop']['first']:
        #    self._last_seen = None
        try:
            if self._varlist:
                # Consider multiple parameters.
                # This automatically behaves like a OR evaluation of the multiple variables.
                compare_to = [resolve_variable(var, context) for var in self._varlist]
            else:
                compare_to = self.nodelist_true.render(context)
        except VariableDoesNotExist:
            compare_to = None        

        if  compare_to != self._last_seen:
            firstloop = (self._last_seen == None)
            self._last_seen = compare_to
            #context.push()
            #context['ifchanged'] = {'firstloop': firstloop}
            content = self.nodelist_true.render(context)
            #context.pop()
            return content
        else:
            if self.nodelist_false:
                return self.nodelist_false.render(context)
            else:
                return ''

#@register.tag
def myifchanged(parser, token):
    """
    Check if a value has changed from the last iteration of a loop.

    The 'myifchanged' block tag is used within a loop. It has two possible uses.

    1. Checks its own rendered contents against its previous state and only
       displays the content if it has changed. For example, this displays a list of
       days, only displaying the month if it changes::

            <h1>Archive for {{ year }}</h1>

            {% for date in days %}
                {% myifchanged %}<h3>{{ date|date:"F" }}</h3>{% endmyifchanged %}
                <a href="{{ date|date:"M/d"|lower }}/">{{ date|date:"j" }}</a>
            {% endfor %}

    2. If given a variable, check whether that variable has changed. For example, the
       following shows the date every time it changes, but only shows the hour if both
       the hour and the date have changed::

            {% for date in days %}
                {% myifchanged date.date %} {{ date.date }} {% endmyifchanged %}
                {% myifchanged date.hour date.date %}
                    {{ date.hour }}
                {% endmyifchanged %}
            {% endfor %}
    """
    bits = token.contents.split()
    nodelist_true = parser.parse(('else', 'endmyifchanged'))
    token = parser.next_token()
    if token.contents == 'else':
        nodelist_false = parser.parse(('endmyifchanged',))
        parser.delete_first_token()
    else:
        nodelist_false = NodeList()
    return MyIfChangedNode(nodelist_true, nodelist_false, *bits[1:])
myifchanged = register.tag(myifchanged)


class CycleValueNode(Node):
    def __init__(self, cyclenode):
        self.cyclenode = cyclenode

    def render(self, context):
	return self.cyclenode.cyclevars[self.cyclenode.counter % self.cyclenode.cyclevars_len]

def cyclevalue(parser, token):
    args = token.contents.split()
    if len(args) == 2:
        name = args[1]
        if not hasattr(parser, '_namedCycleNodes'):
            raise TemplateSyntaxError("No named cycles in template: '%s' is not defined" % name)
        if name not in parser._namedCycleNodes:
            raise TemplateSyntaxError("Named cycle '%s' does not exist" % name)
        return CycleValueNode(parser._namedCycleNodes[name])
    else:
	raise TemplateSyntaxError("Usage: cyclevalue cyclename")
cyclevalue = register.tag(cyclevalue)
