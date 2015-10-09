from django import forms

from ietf.mailtrigger.models import MailTrigger

class CcSelectForm(forms.Form):
    expansions = dict()
    cc_choices = forms.MultipleChoiceField(
                   label='Cc',
                   choices=[],
                   widget=forms.CheckboxSelectMultiple(),
                )

    def __init__(self, mailtrigger_slug, mailtrigger_context, *args, **kwargs):
        super(CcSelectForm,self).__init__(*args,**kwargs)
        mailtrigger = MailTrigger.objects.get(slug=mailtrigger_slug) 
        
        for r in mailtrigger.cc.all():
            self.expansions[r.slug] = r.gather(**mailtrigger_context)

        non_empty_expansions = [x for x in self.expansions if self.expansions[x]]
        self.fields['cc_choices'].initial = non_empty_expansions
        self.fields['cc_choices'].choices = [(t,'%s: %s'%(t,", ".join(self.expansions[t]))) for t in non_empty_expansions]

    def get_selected_addresses(self):
        if self.is_valid():
            addrs = []
            for t in self.cleaned_data['cc_choices']:
                addrs.extend(self.expansions[t])
            return addrs
        else:
            raise forms.ValidationError('Cannot get selected addresses from an invalid form.')
