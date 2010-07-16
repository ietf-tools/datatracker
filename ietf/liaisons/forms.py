from django import forms
from django.template.loader import render_to_string

from ietf.liaisons.models import LiaisonDetail
from ietf.liaisons.accounts import get_person_for_user


class LiaisonForm(forms.ModelForm):

    from_field = forms.ChoiceField()
    organization = forms.CharField()

    fieldsets = ((None, ('from_field', 'replyto', 'organization', 'to_poc',
                         'cc1', 'response_contact', 'technical_contact',
                         'purpose', 'purpose_text', 'deadline_date', 'body',
                         )
                 ),
                )

    class Meta:
        model = LiaisonDetail

    def __init__(self, user, *args, **kwargs):
        super(LiaisonForm, self).__init__(*args, **kwargs)
        self.person = get_person_for_user(user)

    def __unicode__(self):
        return self.as_div()

    def as_div(self):
        return render_to_string('liaisons/liaisonform.html', {'form': self})

    def get_fieldsets(self):
        if not self.fieldsets:
            yield dict(name=None, fields=self)
        else:
            for fieldset, fields in self.fieldsets:
                fieldset_dict = dict(name=fieldset, fields=[])
                for field_name in fields:
                    if field_name in self.fields.keyOrder:
                        fieldset_dict['fields'].append(self[field_name])
                    if not fieldset_dict['fields']:
                        # if there is no fields in this fieldset, we continue to next fieldset
                        continue
                yield fieldset_dict
