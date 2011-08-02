from django.db import models

from ietf.idrfc.idrfc_wrapper import IdRfcWrapper, IdWrapper
from ietf.ietfworkflows.models import StreamedID, Stream


def get_streamed_draft(draft):
    if not draft:
        return None
    try:
        return draft.streamedid
    except StreamedID.DoesNotExist:
        return None


def get_stream_from_draft(draft):
    streamedid = get_streamed_draft(draft)
    if streamedid:
        return streamedid.stream
    return False


def get_stream_by_name(stream_name):
    try:
        return Stream.objects.get(name=stream_name)
    except Stream.DoesNotExist:
        return None


def get_stream_from_id(stream_id):
    try:
        return Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        return None


def _set_stream_automatically(draft, stream):
    (streamed, created) = StreamedID.objects.get_or_create(draft=draft)
    if created:
        streamed.stream = stream
        streamed.save()
    return


def get_stream_from_wrapper(idrfc_wrapper):
    idwrapper = None
    if isinstance(idrfc_wrapper, IdRfcWrapper):
        idwrapper = idrfc_wrapper.id
    elif isinstance(idrfc_wrapper, IdWrapper):
        idwrapper = idrfc_wrapper
    if not idwrapper:
        return None
    draft = idwrapper._draft
    stream = get_stream_from_draft(draft)
    if stream == False:
        stream_id = idwrapper.stream_id()
        stream = get_stream_from_id(stream_id)
        _set_stream_automatically(draft, stream)
        return stream
    else:
        return stream
    return None


def set_stream_for_draft(draft, stream):
    (streamed, created) = StreamedID.objects.get_or_create(draft=draft)
    if streamed.stream != stream:
        streamed.stream = stream
        streamed.group = None
        streamed.save()
    return streamed.stream
