from django.shortcuts import render, get_object_or_404

from ietf.message.models import Message


def message(request, message_id, group_type):
    possible_messages = Message.objects.filter(related_groups__type=group_type)

    message = get_object_or_404(possible_messages, id=message_id)
    
    return render(request, "message/message.html", {"message":message } )
