from django import template
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.ietfauth.utils import has_role
from ietf.group.models import Group
from ietf.name.models import StreamName

register = template.Library()

@register.inclusion_tag('base/streams_menu.html', takes_context=True)
def streams_menu(context):
    user = context["request"].user

    editable_streams = []

    if user.is_authenticated():
        streams = StreamName.objects.exclude(slug="legacy")

        if has_role(user, "Secretariat"):
            editable_stream = streams
        else:
            acronyms = Group.objects.filter(acronym__in=(s.slug for s in streams),
                                            role__name="chair",
                                            role__person__user=user).distinct().values_list("acronym", flat=True)

            for s in streams:
                if s.slug in acronyms:
                    editable_streams.append(s)

    return { 'editable_streams': streams }
