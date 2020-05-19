from django import template
import debug                            # pyflakes:ignore

register = template.Library()


class OriginNode(template.Node):
    def __init__(self, origin=None):
        # template file path if the template comes from a file:
        self.origin = origin

    def render(self, context):
        if self.origin:
            return "<!-- template: %s -->" % self.origin
        else:
            return ""

@register.tag
def origin(parser, token):
    """
    Returns a node which renders the 
    """
    if hasattr(token, "source"):
        origin, source = token.source
        return OriginNode(origin=origin)
    else:
        return OriginNode()
