import datetime

from django import forms

from ietf.iesg.models import TelechatDate
from ietf.doc.models import Document

class TelechatForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False, help_text="Page counts are the current page counts for the telechat, before this telechat date edit is made.")
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        init = kwargs['initial'].get("telechat_date")
        if init and init not in dates:
            dates.insert(0, init)

        self.page_count = {}
        choice_display = {}
        for d in dates:
          self.page_count[d] = sum([doc.pages for doc in Document.objects.filter(docevent__telechatdocevent__telechat_date=d,type='draft').distinct() if doc.telechat_date()==d])
          choice_display[d] = '%s (%s pages)' % (d.strftime("%Y-%m-%d"),self.page_count[d])
        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, choice_display[d]) for d in dates]

from ietf.person.models import Person

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type='area').order_by('name'),
                                label="Shepherding AD", empty_label="(None)", required=True)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

class NotifyForm(forms.Form):
    notify = forms.CharField(max_length=255, help_text="List of email addresses to receive state notifications, separated by comma.", label="Notification list", required=False)

    def clean_notify(self):
        addrspecs = [x.strip() for x in self.cleaned_data["notify"].split(',')]
        return ', '.join(addrspecs)
