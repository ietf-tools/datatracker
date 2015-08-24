from django import forms

from ietf.mailtoken.models import MailToken

class CcSelectForm(forms.Form):
    expansions = dict()
    cc_tokens = forms.MultipleChoiceField(
                   label='Cc',
                   choices=[],
                   widget=forms.CheckboxSelectMultiple(attrs={'frob':'knob'}),
                )

    def __init__(self, mailtoken_slug, mailtoken_context, *args, **kwargs):
        super(CcSelectForm,self).__init__(*args,**kwargs)
        mailtoken = MailToken.objects.get(slug=mailtoken_slug) 
        
        for r in mailtoken.cc.all():
            self.expansions[r.slug] = r.gather(**mailtoken_context)

        non_empty_expansions = [x for x in self.expansions if self.expansions[x]]
        self.fields['cc_tokens'].initial = non_empty_expansions
        self.fields['cc_tokens'].choices = [(t,'%s: %s'%(t,", ".join(self.expansions[t]))) for t in non_empty_expansions]

    def get_selected_addresses(self):
        if self.is_valid():
            addrs = []
            for t in self.cleaned_data['cc_tokens']:
                addrs.extend(self.expansions[t])
            return addrs
        else:
            raise forms.ValidationError('Cannot get selected addresses from an invalid form.')
