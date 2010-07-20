from django import forms
from django.template.loader import render_to_string

from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user)
from ietf.liaisons.models import LiaisonDetail
from ietf.liaisons.utils import IETFHierarchyManager
from ietf.liaisons.widgets import FromWidget, ReadOnlyWidget


class LiaisonForm(forms.ModelForm):

    from_field = forms.ChoiceField(widget=FromWidget, label=u'From')
    replyto = forms.CharField(label=u'Reply to')
    organization = forms.ChoiceField()
    to_poc = forms.CharField(widget=ReadOnlyWidget, label="POC")
    cc1 = forms.CharField(widget=ReadOnlyWidget, label="CC")

    fieldsets = (('From', ('from_field', 'replyto')),
                 ('To', ('organization', 'to_poc')),
                 ('Other email addresses', ('response_contact', 'technical_contact', 'cc1')),
                 ('Purpose', ('purpose', 'purpose_text', 'deadline_date')),
                 ('Body', ('body', )),
                )

    class Meta:
        model = LiaisonDetail

    class Media:
        js = ("/js/jquery-1.4.2.min.js",
              "/js/liaisons.js", )

        css = {'all': ("/css/liaisons.css", )}

    def __init__(self, user, *args, **kwargs):
        super(LiaisonForm, self).__init__(*args, **kwargs)
        self.hm = IETFHierarchyManager()
        self.person = get_person_for_user(user)
        self.set_from_field()
        self.set_replyto_field()
        self.set_organization_field()

    def __unicode__(self):
        return self.as_div()

    def set_from_field(self):
        assert NotImplemented

    def set_replyto_field(self):
        email = self.person.email()
        self.fields['replyto'].initial = email and email[1]

    def set_organization_field(self):
        assert NotImplemented

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


class IncomingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        sdo_managed = [i.sdo for i in self.person.liaisonmanagers_set.all()]
        sdo_authorized = [i.sdo for i in self.person.sdoauthorizedindividual_set.all()]
        sdos = set(sdo_managed).union(sdo_authorized)
        self.fields['from_field'].choices = [(i.pk, i.sdo_name) for i in sdos]
        self.fields['from_field'].widget.submitter = unicode(self.person)

    def set_organization_field(self):
        self.fields['organization'].choices = self.hm.get_all_decorated_entities()


class OutgoingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        pass

    def set_organization_field(self):
        pass


def liaison_form_factory(request):
    user = request.user
    if can_add_incoming_liaison(user):
        return IncomingLiaisonForm(user)
    elif can_add_outgoing_liaison(user):
        return OutgoingLiaisonForm(user)
    return None
