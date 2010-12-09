from workflows.utils import get_workflow_for_object, set_workflow_for_object

from ietf.ietfworkflows.models import WGWorkflow


def get_workflow_for_wg(wg):
    workflow = get_workflow_for_object(wg)
    if not workflow:
        try:
            workflow = WGWorkflow.objects.get(name='Default WG Workflow')
            set_workflow_for_object(wg, workflow)
        except WGWorkflow.DoesNotExist:
            return None
    return workflow

