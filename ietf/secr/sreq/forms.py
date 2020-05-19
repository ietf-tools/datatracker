# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms

import debug                            # pyflakes:ignore

from ietf.name.models import TimerangeName
from ietf.group.models import Group
from ietf.meeting.models import ResourceAssociation, Constraint
from ietf.person.fields import SearchablePersonsField
from ietf.utils.html import clean_text_field

# -------------------------------------------------
# Globals
# -------------------------------------------------

NUM_SESSION_CHOICES = (('','--Please select'),('1','1'),('2','2'))
# LENGTH_SESSION_CHOICES = (('','--Please select'),('1800','30 minutes'),('3600','1 hour'),('5400','1.5 hours'), ('7200','2 hours'),('9000','2.5 hours'))
LENGTH_SESSION_CHOICES = (('','--Please select'),('1800','30 minutes'),('3600','1 hour'),('5400','1.5 hours'), ('7200','2 hours'))
VIRTUAL_LENGTH_SESSION_CHOICES = (('','--Please select'),('3000','50 minutes'),('6000','100 minutes'))
SESSION_TIME_RELATION_CHOICES = (('', 'No preference'),) + Constraint.TIME_RELATION_CHOICES
JOINT_FOR_SESSION_CHOICES = (('1', 'First session'), ('2', 'Second session'), ('3', 'Third session'), )

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def allowed_conflicting_groups():
    return Group.objects.filter(type__in=['wg', 'ag', 'rg'], state__in=['bof', 'proposed', 'active'])

def check_conflict(groups, source_group):
    '''
    Takes a string which is a list of group acronyms.  Checks that they are all active groups
    '''
    # convert to python list (allow space or comma separated lists)
    items = groups.replace(',',' ').split()
    active_groups = allowed_conflicting_groups()
    for group in items:
        if group == source_group.acronym:
            raise forms.ValidationError("Cannot declare a conflict with the same group: %s" % group)

        if not active_groups.filter(acronym=group):
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

# -------------------------------------------------
# Forms
# -------------------------------------------------

class GroupSelectForm(forms.Form):
    group = forms.ChoiceField()

    def __init__(self,*args,**kwargs):
        choices = kwargs.pop('choices')
        super(GroupSelectForm, self).__init__(*args,**kwargs)
        self.fields['group'].widget.choices = choices


class NameModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, name):
        return name.desc

    
class SessionForm(forms.Form):
    num_session = forms.ChoiceField(choices=NUM_SESSION_CHOICES)
    length_session1 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES)
    length_session2 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES,required=False)
    session_time_relation = forms.ChoiceField(choices=SESSION_TIME_RELATION_CHOICES, required=False)
    length_session3 = forms.ChoiceField(choices=LENGTH_SESSION_CHOICES,required=False)
    attendees = forms.IntegerField()
    # FIXME: it would cleaner to have these be
    # ModelMultipleChoiceField, and just customize the widgetry, that
    # way validation comes for free
    conflict1 = forms.CharField(max_length=255,required=False)
    conflict2 = forms.CharField(max_length=255,required=False)
    conflict3 = forms.CharField(max_length=255,required=False)
    joint_with_groups = forms.CharField(max_length=255,required=False)
    joint_for_session = forms.ChoiceField(choices=JOINT_FOR_SESSION_CHOICES, required=False)
    comments = forms.CharField(max_length=200,required=False)
    wg_selector1 = forms.ChoiceField(choices=[],required=False)
    wg_selector2 = forms.ChoiceField(choices=[],required=False)
    wg_selector3 = forms.ChoiceField(choices=[],required=False)
    wg_selector4 = forms.ChoiceField(choices=[],required=False)
    third_session = forms.BooleanField(required=False)
    resources     = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,required=False)
    bethere       = SearchablePersonsField(label="Must be present", required=False)
    timeranges    = NameModelMultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False,
                                                 queryset=TimerangeName.objects.all())
    adjacent_with_wg = forms.ChoiceField(required=False)

    def __init__(self, group, *args, **kwargs):
        if 'hidden' in kwargs:
            self.hidden = kwargs.pop('hidden')
        else:
            self.hidden = False

        self.group = group

        super(SessionForm, self).__init__(*args, **kwargs)
        self.fields['num_session'].widget.attrs['onChange'] = "stat_ls(this.selectedIndex);"
        self.fields['length_session1'].widget.attrs['onClick'] = "if (check_num_session(1)) this.disabled=true;"
        self.fields['length_session2'].widget.attrs['onClick'] = "if (check_num_session(2)) this.disabled=true;"
        self.fields['length_session3'].widget.attrs['onClick'] = "if (check_third_session()) { this.disabled=true;}"
        self.fields['comments'].widget = forms.Textarea(attrs={'rows':'3','cols':'65'})

        other_groups = list(allowed_conflicting_groups().exclude(pk=group.pk).values_list('acronym', 'acronym').order_by('acronym'))
        self.fields['adjacent_with_wg'].choices = [('', '--No preference')] + other_groups
        group_acronym_choices = [('','--Select WG(s)')] + other_groups
        for i in range(1, 5):
            self.fields['wg_selector{}'.format(i)].choices = group_acronym_choices

        # disabling handleconflictfield (which only enables or disables form elements) while we're hacking the meaning of the three constraints currently in use:
        #self.fields['wg_selector1'].widget.attrs['onChange'] = "document.form_post.conflict1.value=document.form_post.conflict1.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(1);"
        #self.fields['wg_selector2'].widget.attrs['onChange'] = "document.form_post.conflict2.value=document.form_post.conflict2.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(2);"
        #self.fields['wg_selector3'].widget.attrs['onChange'] = "document.form_post.conflict3.value=document.form_post.conflict3.value + ' ' + this.options[this.selectedIndex].value; return handleconflictfield(3);"
        self.fields['wg_selector1'].widget.attrs['onChange'] = "document.form_post.conflict1.value=document.form_post.conflict1.value + ' ' + this.options[this.selectedIndex].value; return 1;"
        self.fields['wg_selector2'].widget.attrs['onChange'] = "document.form_post.conflict2.value=document.form_post.conflict2.value + ' ' + this.options[this.selectedIndex].value; return 1;"
        self.fields['wg_selector3'].widget.attrs['onChange'] = "document.form_post.conflict3.value=document.form_post.conflict3.value + ' ' + this.options[this.selectedIndex].value; return 1;"
        self.fields['wg_selector4'].widget.attrs['onChange'] = "document.form_post.joint_with_groups.value=document.form_post.joint_with_groups.value + ' ' + this.options[this.selectedIndex].value; return 1;"

        # disabling check_prior_conflict javascript while we're hacking the meaning of the three constraints currently in use
        #self.fields['wg_selector2'].widget.attrs['onClick'] = "return check_prior_conflict(2);"
        #self.fields['wg_selector3'].widget.attrs['onClick'] = "return check_prior_conflict(3);"
        
        self.fields['third_session'].widget.attrs['onClick'] = "if (document.form_post.num_session.selectedIndex < 2) { alert('Cannot use this field - Number of Session is not set to 2'); return false; } else { if (this.checked==true) { document.form_post.length_session3.disabled=false; } else { document.form_post.length_session3.value=0;document.form_post.length_session3.disabled=true; } }"
        self.fields["resources"].choices = [(x.pk,x.desc) for x in ResourceAssociation.objects.filter(name__used=True).order_by('name__order') ]

        # check third_session checkbox if instance and length_session3
        # assert False, (self.instance, self.fields['length_session3'].initial)
        if self.initial and 'length_session3' in self.initial:
            if self.initial['length_session3'] != '0' and self.initial['length_session3'] != None:
                self.fields['third_session'].initial = True

        if self.hidden:
            for key in list(self.fields.keys()):
                self.fields[key].widget = forms.HiddenInput()
            self.fields['resources'].widget = forms.MultipleHiddenInput()
            self.fields['timeranges'].widget = forms.MultipleHiddenInput()

    def clean_conflict1(self):
        conflict = self.cleaned_data['conflict1']
        check_conflict(conflict, self.group)
        return conflict
    
    def clean_conflict2(self):
        conflict = self.cleaned_data['conflict2']
        check_conflict(conflict, self.group)
        return conflict
    
    def clean_conflict3(self):
        conflict = self.cleaned_data['conflict3']
        check_conflict(conflict, self.group)
        return conflict

    def clean_joint_with_groups(self):
        groups = self.cleaned_data['joint_with_groups']
        check_conflict(groups, self.group)
        return groups

    def clean_comments(self):
        return clean_text_field(self.cleaned_data['comments'])

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
        if data.get('num_session','') == '2':
            if not data['length_session2']:
                raise forms.ValidationError('You must enter a length for all sessions')
        else:
            if data.get('session_time_relation'):
                raise forms.ValidationError('Time between sessions can only be used when two '
                                            'sessions are requested.')
            if data['joint_for_session'] == '2':
                raise forms.ValidationError('The second session can not be the joint session, '
                                            'because you have not requested a second session.')

        if data.get('third_session',False):
            if not data['length_session2'] or not data.get('length_session3',None):
                raise forms.ValidationError('You must enter a length for all sessions')
        elif data['joint_for_session'] == '3':
                raise forms.ValidationError('The third session can not be the joint session, '
                                            'because you have not requested a third session.')
        
        return data


class VirtualSessionForm(SessionForm):
    '''A SessionForm customized for special virtual meeting requirements'''
    length_session1 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES)
    length_session2 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES,required=False)
    length_session3 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES,required=False)
    attendees = forms.IntegerField(required=False)


class ToolStatusForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows':'3','cols':'80'}), strip=False)

