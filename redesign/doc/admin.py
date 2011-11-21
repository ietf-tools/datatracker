from django.utils.safestring import mark_safe
from django.contrib import admin
from django import forms

from models import *
from redesign.person.models import *
from redesign.doc.utils import get_state_types

class StateTypeAdmin(admin.ModelAdmin):
    list_display = ["slug", "label"]
admin.site.register(StateType, StateTypeAdmin)

class StateAdmin(admin.ModelAdmin):
    list_display = ["slug", "type", 'name', 'order', 'desc']
    filter_horizontal = ["next_states"]
admin.site.register(State, StateAdmin)

class DocAliasInline(admin.TabularInline):
    model = DocAlias
    extra = 1

# document form for managing states in a less confusing way

class StatesWidget(forms.SelectMultiple):
    """Display all applicable states as separate select boxes,
    requires 'instance' have been set on the widget."""
    def render(self, name, value, attrs=None, choices=()):

        types = StateType.objects.filter(slug__in=get_state_types(self.instance)).order_by("slug")
        
        categorized_choices = []
        for t in types:
            states = State.objects.filter(type=t).select_related()
            if states:
                categorized_choices.append((t.label, states))

        html = []
        first = True
        for label, states in categorized_choices:
            htmlid = "id_%s_%s" % (name, label)
            
            html.append('<div style="clear:both;padding-top:%s">' % ("1em" if first else "0.5em"))
            html.append(u'<label for="%s">%s:</label>' % (htmlid, label))
            html.append(u'<select name="%s" id="%s">' % (name, htmlid))
            html.append(u'<option value="">-----------</option>')
            for s in states:
                html.append('<option %s value="%s">%s</option>' % ("selected" if s.pk in value else "", s.pk, s.name))
            html.append(u'</select>')
            html.append("</div>")
            
            first = False
            
        return mark_safe(u"".join(html))

class StatesField(forms.ModelMultipleChoiceField):
    def __init__(self, *args, **kwargs):
        # use widget with multiple select boxes
        kwargs['widget'] = StatesWidget
        super(StatesField, self).__init__(*args, **kwargs)
        
    def clean(self, value):
        if value and isinstance(value, (list, tuple)):
            # remove "", in case a state is reset
            value = [x for x in value if x]
        return super(StatesField, self).clean(value)
    
class DocumentForm(forms.ModelForm):
    states = StatesField(queryset=State.objects.all(), required=False)
    
    def __init__(self, *args, **kwargs):
        super(DocumentForm, self).__init__(*args, **kwargs)

        # we don't normally have access to the instance in the widget
        # so set it here
        self.fields["states"].widget.instance = self.instance

    class Meta:
        model = Document

class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'rev', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['name']
    list_filter = ['type']
    raw_id_fields = ['authors', 'related', 'group', 'shepherd', 'ad']
    inlines = [DocAliasInline]
    form = DocumentForm

    def state(self, instance):
        return self.get_state()

admin.site.register(Document, DocumentAdmin)

class DocHistoryAdmin(admin.ModelAdmin):
    list_display = ['doc', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['doc__name']
    ordering = ['time', 'doc', 'rev']
    raw_id_fields = ['doc', 'authors', 'related', 'group', 'shepherd', 'ad']

    def state(self, instance):
        return self.get_state()

admin.site.register(DocHistory, DocHistoryAdmin)

class DocAliasAdmin(admin.ModelAdmin):
    list_display = [ 'name', 'document_link', ]
    search_fields = [ 'name', 'document__name', ]
    raw_id_fields = ['document']
admin.site.register(DocAlias, DocAliasAdmin)


# events

class DocEventAdmin(admin.ModelAdmin):
    list_display = ["doc", "type", "by_raw", "time"]
    raw_id_fields = ["doc", "by"]

    def by_raw(self, instance):
        return instance.by_id
    by_raw.short_description = "By"
    
admin.site.register(DocEvent, DocEventAdmin)

admin.site.register(NewRevisionDocEvent, DocEventAdmin)
admin.site.register(WriteupDocEvent, DocEventAdmin)
admin.site.register(StatusDateDocEvent, DocEventAdmin)
admin.site.register(LastCallDocEvent, DocEventAdmin)
admin.site.register(TelechatDocEvent, DocEventAdmin)

class BallotPositionDocEventAdmin(DocEventAdmin):
    raw_id_fields = ["doc", "by", "ad"]

admin.site.register(BallotPositionDocEvent, BallotPositionDocEventAdmin)
    
