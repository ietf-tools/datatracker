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


def get_chair_model(stream):
    model_str = stream.group_chair_model
    if not model_str:
        return None
    try:
        app, model = model_str.split('.', 1)
    except ValueError:
        return None
    chair_model = models.get_model(app, model)
    if not chair_model:
        return
    return chair_model


def _get_group_from_acronym(group_model_str, acronym):
    try:
        app, model = group_model_str.split('.', 1)
    except ValueError:
        return None
    group_model = models.get_model(app, model)
    if not group_model:
        return
    if 'acronym' in group_model._meta.get_all_field_names():
        try:
            return group_model._default_manager.get(acronym=acronym)
        except group_model.DoesNotExist:
            return None
    elif 'group_acronym' in group_model._meta.get_all_field_names():
        try:
            return group_model._default_manager.get(group_acronym__acronym=acronym)
        except group_model.DoesNotExist:
            return None
    else:
        return None


def _set_stream_automatically(draft, stream):
    streamed = StreamedID.objects.create(stream=stream, draft=draft)
    if not stream or not stream.with_groups:
        return
    try:
        draft_literal, stream_name, group_name, extra = draft.filename.split('-', 3)
        if stream_name.lower() == stream.name.lower():
            group = _get_group_from_acronym(stream.group_model, group_name)
            if group:
                streamed.group = group
                streamed.save()
    except ValueError:
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
