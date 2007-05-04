from django import newforms as forms
from itertools import chain
from ietf.idtracker.models import IDState, IDStatus, GroupIETF
from ietf.idindex.models import orgs

class IDIndexSearchForm(forms.Form):
    filename = forms.CharField(max_length=100, label='Filename (Full or Partial):', widget=forms.TextInput(attrs={'size': 30}))
    id_tracker_state_id = forms.ChoiceField(choices=chain((('', 'All/Any'),),
	[(state.document_state_id, state.state) for state in IDState.objects.all()]), label='I-D Tracker State:')
    wg_id = forms.ChoiceField(choices=chain((('', 'All/Any'),),
	[(wg.group_acronym_id, wg.group_acronym.acronym) for wg in GroupIETF.objects.all().select_related().order_by('acronym.acronym')]), label='Working Group:')
    other_group = forms.ChoiceField(choices=chain((('', 'All/Any'),),
	[(org['key'], org['name']) for org in orgs]), label='Other Group:')
    status_id = forms.ChoiceField(choices=chain((('', 'All/Any'),),
	[(status.status_id, status.status) for status in IDStatus.objects.all()]), label='I-D Status:')
    last_name = forms.CharField(max_length=50)
    first_name = forms.CharField(max_length=50)
