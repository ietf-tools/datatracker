import datetime
from email.utils import parseaddr

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms.util import ErrorList
from django.forms.fields import email_re
from django.template.loader import render_to_string

from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user, is_ietf_liaison_manager)
from ietf.liaisons.models import LiaisonDetail, Uploads, OutgoingLiaisonApproval, SDOs
from ietf.liaisons.utils import IETFHM
from ietf.liaisons.widgets import (FromWidget, ReadOnlyWidget, ButtonWidget,
                                   ShowAttachmentsWidget, RelatedLiaisonWidget)


class UploadForm(forms.Form):

    txt = forms.FileField(label=u'.txt format', required=True)
    xml = forms.FileField(label=u'.xml format', required=False)
    pdf = forms.FileField(label=u'.pdf format', required=False)
    ps = forms.FileField(label=u'.ps format', required=False)

    fieldsets = [('Upload a draft', ('txt', 'xml', 'pdf', 'ps'))]

    class Media:
        css = {'all': ("/css/liaisons.css", )}

    def __unicode__(self):
        return self.as_div()

    def as_div(self):
        return render_to_string('submit/submitform.html', {'form': self})

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
