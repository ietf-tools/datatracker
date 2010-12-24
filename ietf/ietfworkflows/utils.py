import copy

from workflows.utils import get_workflow_for_object, set_workflow_for_object

from ietf.ietfworkflows.models import WGWorkflow


def get_default_workflow_for_wg():
    try:
        workflow = WGWorkflow.objects.get(name='Default WG Workflow')
        return workflow
    except WGWorkflow.DoesNotExist:
        return None
    
def clone_transition(transition):
    new = copy.copy(transition)
    new.pk = None
    new.save()

    # Reference original initial states
    for state in transition.states.all():
        new.states.add(state)
    return new

def clone_workflow(workflow, name):
    new = WGWorkflow.objects.create(name=name, initial_state=workflow.initial_state)

    # Reference default states
    for state in workflow.states.all():
        new.selected_states.add(state)

    # Reference default annotation tags
    for tag in workflow.annotation_tags.all():
        new.selected_tags.add(tag)

    # Reference cloned transitions
    for transition in workflow.transitions.all():
        new.transitions.add(clone_transition(transition))
    return new

def get_workflow_for_wg(wg):
    workflow = get_workflow_for_object(wg)
    try:
        workflow = workflow and workflow.wgworkflow
    except WGWorkflow.DoesNotExist:
        workflow = None
    if not workflow:
        workflow = get_default_workflow_for_wg()
        if not workflow:
            return None
        workflow = clone_workflow(workflow, name='%s workflow' % wg)
        set_workflow_for_object(wg, workflow)
    return workflow
