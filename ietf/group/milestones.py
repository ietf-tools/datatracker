# group milestone editing views

import datetime
import calendar
import json

from django import forms
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from ietf.doc.models import Document, DocEvent
from ietf.doc.utils import get_chartering_type
from ietf.group.models import GroupMilestone, MilestoneGroupEvent
from ietf.group.utils import (save_milestone_in_history, can_manage_group_type, milestone_reviewer_for_group_type,
                              get_group_or_404)
from ietf.name.models import GroupMilestoneStateName
from ietf.group.mails import email_milestones_changed

def json_doc_names(docs):
    return json.dumps([{"id": doc.pk, "name": doc.name } for doc in docs])

def parse_doc_names(s):
    return Document.objects.filter(pk__in=[x.strip() for x in s.split(",") if x.strip()], type="draft")

class MilestoneForm(forms.Form):
    id = forms.IntegerField(required=True, widget=forms.HiddenInput)

    desc = forms.CharField(max_length=500, label="Milestone:", required=True)
    due_month = forms.TypedChoiceField(choices=(), required=True, coerce=int)
    due_year = forms.TypedChoiceField(choices=(), required=True, coerce=int)
    resolved_checkbox = forms.BooleanField(required=False, label="Resolved")
    resolved = forms.CharField(max_length=50, required=False)

    delete = forms.BooleanField(required=False, initial=False)

    docs = forms.CharField(max_length=10000, required=False)

    accept = forms.ChoiceField(choices=(("accept", "Accept"), ("reject", "Reject and delete"), ("noaction", "No action")),
                               required=False, initial="noaction", widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""

        m = self.milestone = kwargs.pop("instance", None)

        self.needs_review = kwargs.pop("needs_review", False)
        can_review = not self.needs_review

        if m:
            self.needs_review = m.state_id == "review"

            if not "initial" in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"].update(dict(id=m.pk,
                                          desc=m.desc,
                                          due_month=m.due.month,
                                          due_year=m.due.year,
                                          resolved_checkbox=bool(m.resolved),
                                          resolved=m.resolved,
                                          docs=",".join(m.docs.values_list("pk", flat=True)),
                                          delete=False,
                                          accept="noaction" if can_review and self.needs_review else None,
                                          ))

            kwargs["prefix"] = "m%s" % m.pk

        super(MilestoneForm, self).__init__(*args, **kwargs)

        # set choices for due date
        this_year = datetime.date.today().year

        self.fields["due_month"].choices = [(month, datetime.date(this_year, month, 1).strftime("%B")) for month in range(1, 13)]

        years = [ y for y in range(this_year, this_year + 10)]

        initial = self.initial.get("due_year")
        if initial and initial not in years:
            years.insert(0, initial)

        self.fields["due_year"].choices = zip(years, map(str, years))

        # figure out what to prepopulate many-to-many field with
        pre = ""
        if not self.is_bound:
            pre = self.initial.get("docs", "")
        else:
            pre = self["docs"].data or ""

        # this is ugly, but putting it on self["docs"] is buggy with a
        # bound/unbound form in Django 1.2
        self.docs_names = parse_doc_names(pre)
        self.docs_prepopulate = json_doc_names(self.docs_names)

        # calculate whether we've changed
        self.changed = self.is_bound and (not self.milestone or any(unicode(self[f].data) != unicode(self.initial[f]) for f in self.fields.iterkeys()))

    def clean_docs(self):
        s = self.cleaned_data["docs"]
        return Document.objects.filter(pk__in=[x.strip() for x in s.split(",") if x.strip()], type="draft")

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
    if not can_manage_group_type(request.user, group.type_id):
        if group.role_set.filter(name="chair", person__user=request.user):
            if milestone_set == "current":
                needs_review = True
        else:
            return HttpResponseForbidden("You are not chair of this group.")

    if milestone_set == "current":
        title = "Edit milestones for %s %s" % (group.acronym, group.type.name)
        milestones = group.groupmilestone_set.filter(state__in=("active", "review"))
    elif milestone_set == "charter":
        title = "Edit charter milestones for %s %s" % (group.acronym, group.type.name)
        milestones = group.groupmilestone_set.filter(state="charter")

    forms = []

    milestones_dict = dict((str(m.id), m) for m in milestones)

    def due_month_year_to_date(c):
        y = c["due_year"]
        m = c["due_month"]
        return datetime.date(y, m, calendar.monthrange(y, m)[1])

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
        m.due = due_month_year_to_date(c)
        m.resolved = c["resolved"]

    def save_milestone_form(f):
        c = f.cleaned_data

        if f.milestone:
            m = f.milestone

            named_milestone = 'milestone "%s"' % m.desc
            if milestone_set == "charter":
                named_milestone = "charter " + named_milestone

            if c["delete"]:
                save_milestone_in_history(m)

                m.state_id = "deleted"
                m.save()

                return 'Deleted %s' % named_milestone

            # compute changes
            history = None

            changes = ['Changed %s' % named_milestone]

            if m.state_id == "review" and not needs_review and c["accept"] != "noaction":
                if not history:
                    history = save_milestone_in_history(m)

                if c["accept"] == "accept":
                    m.state_id = "active"
                    changes.append("set state to active from review, accepting new milestone")
                elif c["accept"] == "reject":
                    m.state_id = "deleted"
                    changes.append("set state to deleted from review, rejecting new milestone")


            if c["desc"] != m.desc and not needs_review:
                if not history:
                    history = save_milestone_in_history(m)
                m.desc = c["desc"]
                changes.append('set description to "%s"' % m.desc)


            c_due = due_month_year_to_date(c)
            if c_due != m.due:
                if not history:
                    history = save_milestone_in_history(m)
                changes.append('set due date to %s from %s' % (c_due.strftime("%B %Y"), m.due.strftime("%B %Y")))
                m.due = c_due

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

                m.docs = new_docs

            if len(changes) > 1:
                m.save()

                return ", ".join(changes)

        else: # new milestone
            m = f.milestone = GroupMilestone()
            set_attributes_from_form(f, m)
            m.save()

            m.docs = c["docs"]

            named_milestone = 'milestone "%s"' % m.desc
            if milestone_set == "charter":
                named_milestone = "charter " + named_milestone

            if m.state_id in ("active", "charter"):
                return 'Added %s, due %s' % (named_milestone, m.due.strftime("%B %Y"))
            elif m.state_id == "review":
                return 'Added %s for review, due %s' % (named_milestone, m.due.strftime("%B %Y"))

    finished_milestone_text = "Done"

    form_errors = False

    if request.method == 'POST':
        # parse out individual milestone forms
        for prefix in request.POST.getlist("prefix"):
            if not prefix: # empty form
                continue

            # new milestones have non-existing ids so instance end up as None
            instance = milestones_dict.get(request.POST.get(prefix + "-id", ""), None)
            f = MilestoneForm(request.POST, prefix=prefix, instance=instance,
                              needs_review=needs_review)
            forms.append(f)

            form_errors = form_errors or not f.is_valid()

        action = request.POST.get("action", "review")
        if action == "review":
            for f in forms:
                if not f.is_valid():
                    continue

                # let's fill in the form milestone so we can output it in the template
                if not f.milestone:
                    f.milestone = GroupMilestone()
                set_attributes_from_form(f, f.milestone)
        elif action == "save" and not form_errors:
            changes = []
            for f in forms:
                change = save_milestone_form(f)

                if not change:
                    continue

                if milestone_set == "charter":
                    DocEvent.objects.create(doc=group.charter, type="changed_charter_milestone",
                                            by=request.user.person, desc=change)
                else:
                    MilestoneGroupEvent.objects.create(group=group, type="changed_milestone",
                                                       by=request.user.person, desc=change, milestone=f.milestone)

                changes.append(change)

            if milestone_set == "current":
                email_milestones_changed(request, group, changes)

            if milestone_set == "charter":
                return redirect('doc_view', name=group.charter.canonical_name())
            else:
                return HttpResponseRedirect(group.about_url())
    else:
        for m in milestones:
            forms.append(MilestoneForm(instance=m, needs_review=needs_review))

    can_reset = milestone_set == "charter" and get_chartering_type(group.charter) == "rechartering"

    empty_form = MilestoneForm(needs_review=needs_review)

    forms.sort(key=lambda f: f.milestone.due if f.milestone else datetime.date.max)

    return render(request, 'group/edit_milestones.html',
                  dict(group=group,
                       title=title,
                       forms=forms,
                       form_errors=form_errors,
                       empty_form=empty_form,
                       milestone_set=milestone_set,
                       finished_milestone_text=finished_milestone_text,
                       needs_review=needs_review,
                       reviewer=milestone_reviewer_for_group_type(group_type),
                       can_reset=can_reset))

@login_required
def reset_charter_milestones(request, group_type, acronym):
    """Reset charter milestones to the currently in-use milestones."""
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_milestones:
        raise Http404
    
    if (not can_manage_group_type(request.user, group_type) and
        not group.role_set.filter(name="chair", person__user=request.user)):
        return HttpResponseForbidden("You are not chair of this group.")

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
                                    desc='Deleted milestone "%s"' % m.desc,
                                    by=request.user.person,
                                    )

        # add current
        for m in current_milestones.filter(id__in=milestone_ids):
            new = GroupMilestone.objects.create(group=m.group,
                                                state_id="charter",
                                                desc=m.desc,
                                                due=m.due,
                                                resolved=m.resolved,
                                                )
            new.docs = m.docs.all()

            DocEvent.objects.create(type="changed_charter_milestone",
                                    doc=group.charter,
                                    desc='Added milestone "%s", due %s, from current group milestones' % (new.desc, new.due.strftime("%B %Y")),
                                    by=request.user.person,
                                    )


        return redirect('group_edit_charter_milestones', group_type=group.type_id, acronym=group.acronym)

    return render(request, 'group/reset_charter_milestones.html',
                  dict(group=group,
                       charter_milestones=charter_milestones,
                       current_milestones=current_milestones,
                   ))


def ajax_search_docs(request, group_type, acronym):
    docs = Document.objects.filter(name__icontains=request.GET.get('q',''), type="draft").order_by('name').distinct()[:20]
    return HttpResponse(json_doc_names(docs), content_type='application/json')
