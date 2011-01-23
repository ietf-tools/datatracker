from django import template

from ietf.idrfc.idrfc_wrapper import IdRfcWrapper, IdWrapper
from ietf.ietfworkflows.utils import (get_workflow_for_draft,
                                      get_state_for_draft)
from ietf.ietfworkflows.streams import get_stream_from_wrapper


register = template.Library()


@register.inclusion_tag('ietfworkflows/stream_state.html', takes_context=True)
def stream_state(context, doc):
    request = context.get('request', None)
    user = request and request.user
    data = {}
    stream = get_stream_from_wrapper(doc)
    data.update({'stream': stream})
    if not stream:
        return data

    idwrapper = None
    if isinstance(doc, IdRfcWrapper):
        idwrapper = doc.id
    elif isinstance(doc, IdWrapper):
        idwrapper = doc
    if not idwrapper:
        return data

    draft = getattr(idwrapper, '_draft', None)
    if not draft:
        return data

    workflow = get_workflow_for_draft(draft)
    state = get_state_for_draft(draft)

    data.update({'workflow': workflow,
                 'draft': draft,
                 'state': state})

    return data


@register.inclusion_tag('ietfworkflows/workflow_history_entry.html', takes_context=True)
def workflow_history_entry(context, entry):
    real_entry = entry.get_real_instance()
    return {'entry': real_entry,
            'entry_class': real_entry.__class__.__name__.lower()}
