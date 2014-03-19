from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.message.models import Message


def message(request, message_id, group_type):
    possible_messages = Message.objects.filter(related_groups__type=group_type)

    message = get_object_or_404(possible_messages, id=message_id)
    
    return render_to_response("message/message.html",
                              dict(message=message),
                              context_instance=RequestContext(request))
