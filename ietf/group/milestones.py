# Copyright The IETF Trust 2012-2020, All Rights Reserved
# group milestone editing views

import datetime
import calendar

from django import forms
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

import debug                            # pyflakes:ignore

from ietf.doc.models import DocEvent
from ietf.doc.utils import get_chartering_type
from ietf.doc.fields import SearchableDocumentsField
from ietf.group.models import GroupMilestone, MilestoneGroupEvent
from ietf.group.utils import (save_milestone_in_history, can_manage_group_type, can_manage_group,
                              milestone_reviewer_for_group_type, get_group_or_404, has_role)
from ietf.name.models import GroupMilestoneStateName
from ietf.group.mails import email_milestones_changed
from ietf.utils.fields import DatepickerDateField
from ietf.utils.response import permission_denied

class MilestoneForm(forms.Form):
    id = forms.IntegerField(required=True, widget=forms.HiddenInput)

    desc = forms.CharField(max_length=500, label="Milestone", required=True)
    due = DatepickerDateField(date_format="MM yyyy", picker_settings={"min-view-mode": "months", "autoclose": "1", "view-mode": "years" }, required=True)
    order = forms.IntegerField(required=True, widget=forms.HiddenInput)
    docs = SearchableDocumentsField(label="Drafts", required=False, help_text="Any drafts that the milestone concerns.")
    resolved_checkbox = forms.BooleanField(required=False, label="Resolved")
    resolved = forms.CharField(label="Resolved as", max_length=50, required=False)

    delete = forms.BooleanField(required=False, initial=False)

    review = forms.ChoiceField(label="Review action", help_text="Choose whether to accept or reject the proposed changes.",
                               choices=(("accept", "Accept"), ("reject", "Reject and delete"), ("noaction", "No action")),
                               required=False, initial="noaction", widget=forms.RadioSelect)

    def __init__(self, needs_review, reviewer, desc_editable, *args, **kwargs):
        m = self.milestone = kwargs.pop("instance", None)

        uses_dates = kwargs.pop("uses_dates", True)

        can_review = not needs_review

        if m:
            needs_review = m.state_id == "review"

            if not "initial" in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"].update(dict(id=m.pk,
                                          desc=m.desc,
                                          due=m.due,
                                          order=m.order,
                                          resolved_checkbox=bool(m.resolved),
                                          resolved=m.resolved,
                                          docs=m.docs.all(),
                                          delete=False,
                                          review="noaction" if can_review and needs_review else "",
                                          ))

            kwargs["prefix"] = "m%s" % m.pk

        super(MilestoneForm, self).__init__(*args, **kwargs)

        if not uses_dates:
            self.fields.pop('due')
        else:
            self.fields.pop('order')

        self.fields["resolved"].widget.attrs["data-default"] = "Done"

        if needs_review and self.milestone and self.milestone.state_id != "review":
            self.fields["desc"].widget.attrs["readonly"] = True

        self.changed = False

        if not (needs_review and can_review):
            self.fields["review"].widget = forms.HiddenInput()

        self.needs_review = needs_review

        if not desc_editable:
            self.fields["desc"].widget.attrs["readonly"] = True

    def clean_resolved(self):
        r = self.cleaned_data["resolved"].strip()

        if self.cleaned_data["resolved_checkbox"]:
            if not r:
                raise forms.ValidationError('Please provide explanation (like "Done") for why the milestone is no longer due.')
        else:
            r = ""

        return r

@login_required
def edit_milestones(request, acronym, group_type=None, milestone_set="current"):
    # milestones_set + needs_review: we have several paths into this view
    #  management (IRTF chair/AD/...)/Secr. -> all actions on current + add new
    #  group chair -> limited actions on current + add new for review
    #  (re)charter -> all actions on existing in state charter + add new in state charter
    #
    # For charters we store the history on the charter document to not confuse people.
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_milestones:
        raise Http404

    needs_review = False
    if can_manage_group(request.user, group):
        can_change_uses_milestone_dates = True
        if not can_manage_group_type(request.user, group):
            # The user is chair or similar, not AD:
            can_change_uses_milestone_dates = False
            if milestone_set == "current":
                needs_review = True
    else:
        permission_denied(request, "You are not authorized to edit the milestones of this group.")

    desc_editable = has_role(request.user,["Secretariat","Area Director","IRTF Chair"])

    if milestone_set == "current":
        title = "Edit milestones for %s %s" % (group.acronym, group.type.name)
        milestones = group.groupmilestone_set.filter(state__in=("active", "review"))
    elif milestone_set == "charter":
        title = "Edit charter milestones for %s %s" % (group.acronym, group.type.name)
        milestones = group.groupmilestone_set.filter(state="charter")

    reviewer = milestone_reviewer_for_group_type(group_type)

    forms = []

    milestones_dict = dict((str(m.id), m) for m in milestones)

    def due_month_year_to_date(c):
        if isinstance(c, dict):
            y = c["due"].year
            m = c["due"].month
        else:
            y = c.year
            m = c.month
        first_day, last_day = calendar.monthrange(y, m)
        return datetime.date(y, m, last_day)

    def set_attributes_from_form(f, m):
        c = f.cleaned_data
        m.group = group
        if milestone_set == "current":
            if needs_review:
                m.state = GroupMilestoneStateName.objects.get(slug="review")
            else:
                m.state = GroupMilestoneStateName.objects.get(slug="active")
        elif milestone_set == "charter":
            m.state = GroupMilestoneStateName.objects.get(slug="charter")
        
        m.desc = c["desc"]
        m.resolved = c["resolved"]
        if 'due' in f.fields:
            m.due = due_month_year_to_date(c)
        else:
            m.order = c["order"]

    def milestone_changed(f, m):
        # we assume that validation has run
        if not m or not f.is_valid():
            return True

        c = f.cleaned_data

        changed = (
            c["desc"] != m.desc or
            c["resolved"] != m.resolved or
            set(c["docs"]) != set(m.docs.all()) or
            c.get("review") in ("accept", "reject")
        )
        if 'due' in f.fields:
            changed = changed or due_month_year_to_date(c) != due_month_year_to_date(m.due) 
        else:
            changed = changed or c["order"] != m.order
        return changed

    def save_milestone_form(f):
        c = f.cleaned_data

        if f.milestone:
            m = f.milestone
            initial_state = m.state_id

            named_milestone = 'milestone "%s"' % m.desc
            if milestone_set == "charter":
                named_milestone = "charter " + named_milestone

            # compute changes
            history = None

            if c["delete"]:
                history = save_milestone_in_history(m)
                m.state_id = "deleted"

                changes = ['Deleted %s' % named_milestone]
            else:
                changes = ['Changed %s' % named_milestone]

            if m.state_id == "review" and not needs_review and c["review"] != "noaction":
                if not history:
                    history = save_milestone_in_history(m)

                if c["review"] == "accept":
                    m.state_id = "active"
                    changes.append("set state to active from review, accepting new milestone")
                elif c["review"] == "reject":
                    m.state_id = "deleted"
                    changes.append("set state to deleted from review, rejecting new milestone")


            if c["desc"] != m.desc and not needs_review and desc_editable:
                if not history:
                    history = save_milestone_in_history(m)
                m.desc = c["desc"]
                changes.append('set description to "%s"' % m.desc)

            if 'due' in f.fields:
                c_due = due_month_year_to_date(c)
                m_due = due_month_year_to_date(m.due)
                if c_due != m_due:
                    if not history:
                        history = save_milestone_in_history(m)
                    changes.append('set due date to %s from %s' % (c_due.strftime("%B %Y"), m.due.strftime("%B %Y")))
                    m.due = c_due
            else:
                order = c["order"]
                if order != m.order:
                    if not history:
                        history = save_milestone_in_history(m)
                    changes.append("Milestone order changed from %s to %s" % ( m.order, order ))
                    m.order = order

            resolved = c["resolved"]
            if resolved != m.resolved:
                if resolved and not m.resolved:
                    changes.append('resolved as "%s"' % resolved)
                elif not resolved and m.resolved:
                    changes.append("reverted to not being resolved")
                elif resolved and m.resolved:
                    changes.append('set resolution to "%s"' % resolved)

                if not history:
                    history = save_milestone_in_history(m)

                m.resolved = resolved

            new_docs = set(c["docs"])
            old_docs = set(m.docs.all())
            if new_docs != old_docs:
                added = new_docs - old_docs
                if added:
                    changes.append('added %s to milestone' % ", ".join(d.name for d in added))

                removed = old_docs - new_docs
                if removed:
                    changes.append('removed %s from milestone' % ", ".join(d.name for d in removed))

                if not history:
                    history = save_milestone_in_history(m)
                    
                m.docs.clear()
                m.docs.set(new_docs)

            if len(changes) > 1:
                if c["delete"]:
                    messages.warning(request, "Found conflicting form data: both delete action and milestone changes for '%s'. "
                                              "Ignoring the delete; if deletion is wanted, please mark for deletion without making other changes." % (m.desc, ))
                    m.state_id = initial_state
                    changes[0] = 'Changed %s' % named_milestone
                m.save()
                return ", ".join(changes)

            elif c["delete"]:
                m.save()
                return ", ".join(changes)

        else: # new milestone
            m = f.milestone = GroupMilestone()
            set_attributes_from_form(f, m)
            m.save()

            m.docs.set(c["docs"])

            named_milestone = 'milestone "%s"' % m.desc
            if milestone_set == "charter":
                named_milestone = "charter " + named_milestone

            desc = 'Added %s' % (named_milestone, )
            if m.state_id == 'review':
                desc += ' for review'
            if 'due' in f.fields:
                desc += ', due %s' % (m.due.strftime("%B %Y"), )
            return desc

    form_errors = False

    if request.method == 'POST':

        action = request.POST.get("action", "review")

        if action == "switch":
            if can_change_uses_milestone_dates: 
                if group.uses_milestone_dates:
                    group.uses_milestone_dates=False
                    group.save()
                    for order, milestone in enumerate(group.groupmilestone_set.filter(state_id='active').order_by('due','id')):
                        milestone.order = order
                        milestone.save()
                else:
                    group.uses_milestone_dates=True
                    group.save()
                for m in milestones:
                    forms.append(MilestoneForm(needs_review, reviewer, desc_editable, instance=m, uses_dates=group.uses_milestone_dates))
            else:
                permission_denied(request, "You don't have the required permissions to change the 'uses milestone dates' setting")
        else:
            # parse out individual milestone forms
            for prefix in request.POST.getlist("prefix"):
                if not prefix: # empty form
                    continue

                # new milestones have non-existing ids so instance end up as None
                instance = milestones_dict.get(request.POST.get(prefix + "-id", ""), None)
                f = MilestoneForm(needs_review, reviewer, True, request.POST, prefix=prefix, instance=instance, uses_dates=group.uses_milestone_dates)
                forms.append(f)

                form_errors = form_errors or not f.is_valid()

                f.changed = milestone_changed(f, f.milestone)
                if f.is_valid() and f.cleaned_data.get("review") in ("accept", "reject"):
                    f.needs_review = False

            if action == "review":
                for f in forms:
                    if f.is_valid():
                        # let's fill in the form milestone so we can output it in the template
                        if not f.milestone:
                            f.milestone = GroupMilestone()
                        set_attributes_from_form(f, f.milestone)
            elif action == "save" and not form_errors:
                changes = []
                states = []
                for f in forms:
                    change = save_milestone_form(f)

                    if not change:
                        continue

                    if milestone_set == "charter":
                        DocEvent.objects.create(doc=group.charter, rev=group.charter.rev, type="changed_charter_milestone",
                                                by=request.user.person, desc=change)
                    else:
                        MilestoneGroupEvent.objects.create(group=group, type="changed_milestone",
                                                           by=request.user.person, desc=change, milestone=f.milestone)

                    changes.append(change)
                    states.append(f.milestone.state_id)


                if milestone_set == "current":
                    email_milestones_changed(request, group, changes, states)

                if milestone_set == "charter":
                    return redirect('ietf.doc.views_doc.document_main', name=group.charter.canonical_name())
                else:
                    return HttpResponseRedirect(group.about_url())
    else:
        for m in milestones:
            forms.append(MilestoneForm(needs_review, reviewer, desc_editable, instance=m, uses_dates=group.uses_milestone_dates))

    can_reset = milestone_set == "charter" and get_chartering_type(group.charter) == "rechartering"

    empty_form = MilestoneForm(needs_review, reviewer, True, uses_dates=group.uses_milestone_dates)

    if group.uses_milestone_dates:
        forms.sort(key=lambda f: f.milestone.due if f.milestone else datetime.date.max)
    else:
        forms.sort(key=lambda f: (f.milestone is None, f.milestone.order if f.milestone else None) )

    return render(request, 'group/edit_milestones.html',
                  dict(group=group,
                       title=title,
                       forms=forms,
                       form_errors=form_errors,
                       empty_form=empty_form,
                       all_forms=forms + [empty_form],
                       milestone_set=milestone_set,
                       needs_review=needs_review,
                       reviewer=reviewer,
                       can_reset=can_reset,
                       can_change_uses_milestone_dates=can_change_uses_milestone_dates))

@login_required
def reset_charter_milestones(request, group_type, acronym):
    """Reset charter milestones to the currently in-use milestones."""
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_milestones:
        raise Http404

    if not can_manage_group(request.user, group):
        permission_denied(request, "You are not authorized to change the milestones for this group.")

    current_milestones = group.groupmilestone_set.filter(state="active")
    charter_milestones = group.groupmilestone_set.filter(state="charter")

    if request.method == 'POST':
        try:
            milestone_ids = [int(v) for v in request.POST.getlist("milestone")]
        except ValueError as e:
            return HttpResponseBadRequest("error in list of ids - %s" % e)

        # delete existing
        for m in charter_milestones:
            save_milestone_in_history(m)

            m.state_id = "deleted"
            m.save()

            DocEvent.objects.create(type="changed_charter_milestone",
                                    doc=group.charter,
                                    rev=group.charter.rev,
                                    desc='Deleted milestone "%s"' % m.desc,
                                    by=request.user.person,
                                    )

        # add current
        for m in current_milestones.filter(id__in=milestone_ids):
            new = GroupMilestone.objects.create(group=m.group,
                                                state_id="charter",
                                                desc=m.desc,
                                                due=m.due,
                                                order=m.order,
                                                resolved=m.resolved,
                                                )
            new.docs.clear()
            new.docs.set(m.docs.all())

            if group.uses_milestone_dates:
                desc='Added milestone "%s", due %s, from current group milestones' % (new.desc, new.due.strftime("%B %Y"))
            else:
                desc='Added milestone "%s" from current group milestones' % ( new.desc, )
            DocEvent.objects.create(type="changed_charter_milestone",
                                    doc=group.charter,
                                    rev=group.charter.rev,
                                    desc=desc,
                                    by=request.user.person,
                                    )


        return redirect('ietf.group.milestones.edit_milestones;charter', group_type=group.type_id, acronym=group.acronym)

    return render(request, 'group/reset_charter_milestones.html',
                  dict(group=group,
                       charter_milestones=charter_milestones,
                       current_milestones=current_milestones,
                   ))
