# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms

import debug                            # pyflakes:ignore

from ietf.name.models import TimerangeName, ConstraintName
from ietf.group.models import Group
from ietf.meeting.models import ResourceAssociation, Constraint
from ietf.person.fields import SearchablePersonsField
from ietf.utils.html import clean_text_field
from ietf.utils import log

# -------------------------------------------------
# Globals
# -------------------------------------------------

NUM_SESSION_CHOICES = (('','--Please select'),('1','1'),('2','2'))
# LENGTH_SESSION_CHOICES = (('','--Please select'),('1800','30 minutes'),('3600','1 hour'),('5400','1.5 hours'), ('7200','2 hours'),('9000','2.5 hours'))
LENGTH_SESSION_CHOICES = (('','--Please select'),('3600','60 minutes'),('7200','120 minutes'))
VIRTUAL_LENGTH_SESSION_CHOICES = (('','--Please select'),('3000','50 minutes'),('6000','100 minutes'))
SESSION_TIME_RELATION_CHOICES = (('', 'No preference'),) + Constraint.TIME_RELATION_CHOICES
JOINT_FOR_SESSION_CHOICES = (('1', 'First session'), ('2', 'Second session'), ('3', 'Third session'), )

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def allowed_conflicting_groups():
    return Group.objects.filter(type__in=['wg', 'ag', 'rg', 'rag', 'program'], state__in=['bof', 'proposed', 'active'])

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
    # way validation comes for free (applies to this CharField and the
    # constraints dynamically instantiated in __init__())
    joint_with_groups = forms.CharField(max_length=255,required=False)
    joint_with_groups_selector = forms.ChoiceField(choices=[], required=False)  # group select widget for prev field
    joint_for_session = forms.ChoiceField(choices=JOINT_FOR_SESSION_CHOICES, required=False)
    comments = forms.CharField(max_length=200,required=False)
    third_session = forms.BooleanField(required=False)
    resources     = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,required=False)
    bethere       = SearchablePersonsField(label="Must be present", required=False)
    timeranges    = NameModelMultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False,
                                                 queryset=TimerangeName.objects.all())
    adjacent_with_wg = forms.ChoiceField(required=False)

    def __init__(self, group, meeting, *args, **kwargs):
        if 'hidden' in kwargs:
            self.hidden = kwargs.pop('hidden')
        else:
            self.hidden = False

        self.group = group

        super(SessionForm, self).__init__(*args, **kwargs)
        self.fields['num_session'].widget.attrs['onChange'] = "ietf_sessions.stat_ls(this.selectedIndex);"
        self.fields['length_session1'].widget.attrs['onClick'] = "if (ietf_sessions.check_num_session(1)) this.disabled=true;"
        self.fields['length_session2'].widget.attrs['onClick'] = "if (ietf_sessions.check_num_session(2)) this.disabled=true;"
        self.fields['length_session3'].widget.attrs['onClick'] = "if (ietf_sessions.check_third_session()) { this.disabled=true;}"
        self.fields['comments'].widget = forms.Textarea(attrs={'rows':'3','cols':'65'})

        other_groups = list(allowed_conflicting_groups().exclude(pk=group.pk).values_list('acronym', 'acronym').order_by('acronym'))
        self.fields['adjacent_with_wg'].choices = [('', '--No preference')] + other_groups
        group_acronym_choices = [('','--Select WG(s)')] + other_groups
        self.fields['joint_with_groups_selector'].choices = group_acronym_choices

        # Set up constraints for the meeting
        self._wg_field_data = []
        for constraintname in meeting.group_conflict_types.all():
            # two fields for each constraint: a CharField for the group list and a selector to add entries
            constraint_field = forms.CharField(max_length=255, required=False)
            constraint_field.widget.attrs['data-slug'] = constraintname.slug
            constraint_field.widget.attrs['data-constraint-name'] = str(constraintname).title()
            self._add_widget_class(constraint_field.widget, 'wg_constraint')

            selector_field = forms.ChoiceField(choices=group_acronym_choices, required=False)
            selector_field.widget.attrs['data-slug'] = constraintname.slug  # used by onChange handler
            self._add_widget_class(selector_field.widget, 'wg_constraint_selector')

            cfield_id = 'constraint_{}'.format(constraintname.slug)
            cselector_id = 'wg_selector_{}'.format(constraintname.slug)
            # keep an eye out for field name conflicts
            log.assertion('cfield_id not in self.fields')
            log.assertion('cselector_id not in self.fields')
            self.fields[cfield_id] = constraint_field
            self.fields[cselector_id] = selector_field
            self._wg_field_data.append((constraintname, cfield_id, cselector_id))

        # Show constraints that are not actually used by the meeting so these don't get lost
        self._inactive_wg_field_data = []
        inactive_cnames = ConstraintName.objects.filter(
            is_group_conflict=True  # Only collect group conflicts...
        ).exclude(
            meeting=meeting  # ...that are not enabled for this meeting...
        ).filter(
            constraint__source=group,  # ...but exist for this group...
            constraint__meeting=meeting,  # ... at this meeting.
        ).distinct()

        for inactive_constraint_name in inactive_cnames:
            field_id = 'delete_{}'.format(inactive_constraint_name.slug)
            self.fields[field_id] = forms.BooleanField(required=False, label='Delete this conflict', help_text='Delete this inactive conflict?')
            constraints = group.constraint_source_set.filter(meeting=meeting, name=inactive_constraint_name)
            self._inactive_wg_field_data.append(
                (inactive_constraint_name,
                 ' '.join([c.target.acronym for c in constraints]),
                 field_id)
            )

        self.fields['joint_with_groups_selector'].widget.attrs['onChange'] = "document.form_post.joint_with_groups.value=document.form_post.joint_with_groups.value + ' ' + this.options[this.selectedIndex].value; return 1;"
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

    def wg_constraint_fields(self):
        """Iterates over wg constraint fields

        Intended for use in the template.
        """
        for cname, cfield_id, cselector_id in self._wg_field_data:
            yield cname, self[cfield_id], self[cselector_id]

    def wg_constraint_count(self):
        """How many wg constraints are there?"""
        return len(self._wg_field_data)

    def wg_constraint_field_ids(self):
        """Iterates over wg constraint field IDs"""
        for cname, cfield_id, _ in self._wg_field_data:
            yield cname, cfield_id

    def inactive_wg_constraints(self):
        for cname, value, field_id in self._inactive_wg_field_data:
            yield cname, value, self[field_id]

    def inactive_wg_constraint_count(self):
        return len(self._inactive_wg_field_data)

    def inactive_wg_constraint_field_ids(self):
        """Iterates over wg constraint field IDs"""
        for cname, _, field_id in self._inactive_wg_field_data:
            yield cname, field_id

    @staticmethod
    def _add_widget_class(widget, new_class):
        """Add a new class, taking care in case some already exist"""
        existing_classes = widget.attrs.get('class', '').split()
        widget.attrs['class'] = ' '.join(existing_classes + [new_class])

    def _join_conflicts(self, cleaned_data, slugs):
        """Concatenate constraint fields from cleaned data into a single list"""
        conflicts = []
        for cname, cfield_id, _ in self._wg_field_data:
            if cname.slug in slugs and cfield_id in cleaned_data:
                groups = cleaned_data[cfield_id]
                # convert to python list (allow space or comma separated lists)
                items = groups.replace(',',' ').split()
                conflicts.extend(items)
        return conflicts

    def _validate_duplicate_conflicts(self, cleaned_data):
        """Validate that no WGs appear in more than one constraint that does not allow duplicates

        Raises ValidationError
        """
        # Only the older constraints (conflict, conflic2, conflic3) need to be mutually exclusive.
        all_conflicts = self._join_conflicts(cleaned_data, ['conflict', 'conflic2', 'conflic3'])
        seen = []
        duplicated = []
        errors = []
        for c in all_conflicts:
            if c not in seen:
                seen.append(c)
            elif c not in duplicated:  # only report once
                duplicated.append(c)
                errors.append(forms.ValidationError('%s appears in conflicts more than once' % c))
        return errors

    def clean_joint_with_groups(self):
        groups = self.cleaned_data['joint_with_groups']
        check_conflict(groups, self.group)
        return groups

    def clean_comments(self):
        return clean_text_field(self.cleaned_data['comments'])

    def clean(self):
        super(SessionForm, self).clean()
        data = self.cleaned_data

        # Validate the individual conflict fields
        for _, cfield_id, _ in self._wg_field_data:
            try:
                check_conflict(data[cfield_id], self.group)
            except forms.ValidationError as e:
                self.add_error(cfield_id, e)

        # Skip remaining tests if individual field tests had errors,
        if self.errors:
            return data

        # error if conflicts contain disallowed dupes
        for error in self._validate_duplicate_conflicts(data):
            self.add_error(None, error)

        # verify session_length and num_session correspond
        # if default (empty) option is selected, cleaned_data won't include num_session key
        if data.get('num_session','') == '2':
            if not data['length_session2']:
                self.add_error('length_session2', forms.ValidationError('You must enter a length for all sessions'))
        else:
            if data.get('session_time_relation'):
                self.add_error(
                    'session_time_relation',
                    forms.ValidationError('Time between sessions can only be used when two sessions are requested.')
                )
            if data.get('joint_for_session') == '2':
                self.add_error(
                    'joint_for_session',
                    forms.ValidationError(
                        'The second session can not be the joint session, because you have not requested a second session.'
                    )
                )

        if data.get('third_session', False):
            if not data.get('length_session3',None):
                self.add_error('length_session3', forms.ValidationError('You must enter a length for all sessions'))
        elif data.get('joint_for_session') == '3':
                self.add_error(
                    'joint_for_session',
                    forms.ValidationError(
                        'The third session can not be the joint session, because you have not requested a third session.'
                    )
                )
        
        return data


class VirtualSessionForm(SessionForm):
    '''A SessionForm customized for special virtual meeting requirements'''
    length_session1 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES)
    length_session2 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES,required=False)
    length_session3 = forms.ChoiceField(choices=VIRTUAL_LENGTH_SESSION_CHOICES,required=False)
    attendees = forms.IntegerField(required=False)


class ToolStatusForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows':'3','cols':'80'}), strip=False)

