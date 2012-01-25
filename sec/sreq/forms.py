from django import forms

from ietf.group.models import Group
import os

# -------------------------------------------------
# Globals
# -------------------------------------------------

NUM_SESSION_CHOICES = (('','--Please select'),('1','1'),('2','2'))
LENGTH_SESSION_CHOICES = (('','--Please select'),('3600','1 hour'),('5400','1.5 hours'), ('7200','2 hours'),('9000','2.5 hours'))
WG_CHOICES = list( Group.objects.filter(type__in=('wg','rg'),state__in=('bof','proposed','active')).values_list('acronym','acronym').order_by('acronym'))
WG_CHOICES.insert(0,('','--Select WG(s)'))

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def check_conflict(groups):
    # convert to python list (allow space or comma separated lists)
    items = groups.replace(',',' ').split()
    for group in items:
        if not validate_group(group):
            raise forms.ValidationError("Invalid or inactive group acronym: %s" % group)
            
def join_conflicts(data):
    '''
    Takes a dictionary (ie. data dict from a form) and concatenates all
    conflict fields into one list
    '''
    conflicts = []
    for groups in (data['conflict1'],data['conflict2'],data['conflict3']):
        # convert to python list (allow space or comma separated lists)
        items = groups.replace(',',' ').split()
        conflicts.extend(items)
    return conflicts
    
def validate_group(acronym):
    '''
    Takes a string which is a group acronym.  Returns true if it is an acronym
    of a active group
    '''
    if Group.objects.active_wgs().filter(acronym=acronym):
        return True

    return False

# -------------------------------------------------
# Forms
# -------------------------------------------------

class GroupSelectForm(forms.Form):
    group = forms.ChoiceField()
    
    def __init__(self,*args,**kwargs):
        choices = kwargs.pop('choices')
        super(GroupSelectForm, self).__init__(*args,**kwargs)
        self.fields['group'].widget.choices = choices


class SessionForm(forms.Form):
    num_session = forms.ChoiceField(choices=NUM_SESSION_CHOICES)
    length_session1 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES)
    length_session2 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES,required=False)
    length_session3 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES,required=False)
    attendees = forms.IntegerField()
    conflict1 = forms.CharField(max_length=80,required=False)
    conflict2 = forms.CharField(max_length=80,required=False)
    conflict3 = forms.CharField(max_length=80,required=False)
    comments = forms.CharField(max_length=200,required=False)
    wg_selector1 = forms.ChoiceField(choices=WG_CHOICES,required=False)
    wg_selector2 = forms.ChoiceField(choices=WG_CHOICES,required=False)
    wg_selector3 = forms.ChoiceField(choices=WG_CHOICES,required=False)
    third_session = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(SessionForm, self).__init__(*args, **kwargs)
        self.fields['num_session'].widget.attrs['onChange'] = "stat_ls(this.selectedIndex);"
        self.fields['length_session1'].widget.attrs['onClick'] = "if (check_num_session(1)) this.disabled=true;"
        self.fields['length_session2'].widget.attrs['onClick'] = "if (check_num_session(2)) this.disabled=true;"
        self.fields['length_session3'].widget.attrs['onClick'] = "if (check_third_session()) { this.disabled=true;}"
        self.fields['comments'].widget = forms.Textarea(attrs={'rows':'6','cols':'65'})
        self.fields['wg_selector1'].widget.attrs['onChange'] = "document.form_post.conflict1.value=document.form_post.conflict1.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(1);"
        self.fields['wg_selector2'].widget.attrs['onChange'] = "document.form_post.conflict2.value=document.form_post.conflict2.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(2);"
        self.fields['wg_selector2'].widget.attrs['onClick'] = "return check_prior_conflict(2);"
        self.fields['wg_selector3'].widget.attrs['onChange'] = "document.form_post.conflict3.value=document.form_post.conflict3.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(3);"
        self.fields['wg_selector3'].widget.attrs['onClick'] = "return check_prior_conflict(3);"
        self.fields['third_session'].widget.attrs['onClick'] = "if (document.form_post.num_session.selectedIndex < 2) { alert('Cannot use this field - Number of Session is not set to 2'); return false; } else { if (this.checked==true) { document.form_post.length_session3.disabled=false; } else { document.form_post.length_session3.value=0;document.form_post.length_session3.disabled=true; } }"
        
        # check third_session checkbox if instance and length_session3
        # assert False, (self.instance, self.fields['length_session3'].initial)
        if self.initial and 'length_session3' in self.initial:
            if self.initial['length_session3'] != '0' and self.initial['length_session3'] != None:
                self.fields['third_session'].initial = True
                
    def clean_conflict1(self):
        conflict = self.cleaned_data['conflict1']
        check_conflict(conflict)
        return conflict
    
    def clean_conflict2(self):
        conflict = self.cleaned_data['conflict2']
        check_conflict(conflict)
        return conflict
    
    def clean_conflict3(self):
        conflict = self.cleaned_data['conflict3']
        check_conflict(conflict)
        return conflict
    
    def clean(self):
        super(SessionForm, self).clean()
        data = self.cleaned_data
        if self.errors:
            return self.cleaned_data
            
        # error if conflits contain dupes
        all_conflicts = join_conflicts(data)
        temp = []
        for c in all_conflicts:
            if c not in temp:
                temp.append(c)
            else:
                raise forms.ValidationError('%s appears in conflicts more than once' % c)
        
        # verify session_length and num_session correspond
        # if default (empty) option is selected, cleaned_data won't include num_session key
        if data.get('num_session','') == 2:
            if not data['length_session2']:
                raise forms.ValidationError('You must enter a length for session 2')
        
        if data.get('third_session',False):
            if not data.get('length_session3',None):
                raise forms.ValidationError('Length of third session not selected')
        
        return data
        
class ToolStatusForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows':'3','cols':'80'}))
    
