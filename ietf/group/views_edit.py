# edit/create view for groups

import re
import datetime

from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden, Http404, HttpResponseRedirect
from django.utils.html import mark_safe
from django.contrib.auth.decorators import login_required

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, DocTagName, State
from ietf.doc.utils import get_tags_for_stream_id
from ietf.doc.utils_charter import charter_name_for_group
from ietf.group.models import ( Group, Role, GroupEvent, GroupHistory, GroupStateName,
    GroupStateTransitions, GroupTypeName, GroupURL, ChangeStateGroupEvent )
from ietf.group.utils import save_group_in_history, can_manage_group
from ietf.group.utils import get_group_or_404, setup_default_community_list_for_group
from ietf.ietfauth.utils import has_role
from ietf.person.fields import SearchableEmailsField
from ietf.person.models import Person, Email
from ietf.group.mails import ( email_admin_re_charter, email_personnel_change)
from ietf.utils.ordereddict import insert_after_in_ordered_dict

MAX_GROUP_DELEGATES = 3

class GroupForm(forms.Form):
    name = forms.CharField(max_length=255, label="Name", required=True)
    acronym = forms.CharField(max_length=10, label="Acronym", required=True)
    state = forms.ModelChoiceField(GroupStateName.objects.all(), label="State", required=True)
    chairs = SearchableEmailsField(label="Chairs", required=False, only_users=True)
    secretaries = SearchableEmailsField(label="Secretaries", required=False, only_users=True)
    techadv = SearchableEmailsField(label="Technical Advisors", required=False, only_users=True)
    delegates = SearchableEmailsField(label="Delegates", required=False, only_users=True, max_entries=MAX_GROUP_DELEGATES,
                                      help_text=mark_safe("Chairs can delegate the authority to update the state of group documents - at most %s persons at a given time." % MAX_GROUP_DELEGATES))
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type='area').order_by('name'), label="Shepherding AD", empty_label="(None)", required=False)
    parent = forms.ModelChoiceField(Group.objects.filter(state="active").order_by('name'), empty_label="(None)", required=False)
    list_email = forms.CharField(max_length=64, required=False)
    list_subscribe = forms.CharField(max_length=255, required=False)
    list_archive = forms.CharField(max_length=255, required=False)
    urls = forms.CharField(widget=forms.Textarea, label="Additional URLs", help_text="Format: https://site/path (Optional description). Separate multiple entries with newline. Prefer HTTPS URLs where possible.", required=False)

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group', None)
        self.group_type = kwargs.pop('group_type', False)

        super(self.__class__, self).__init__(*args, **kwargs)

        if self.group_type == "rg":
            self.fields["state"].queryset = self.fields["state"].queryset.exclude(slug__in=("bof", "bof-conc"))

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

        if self.group:
            self.fields['acronym'].widget.attrs['readonly'] = ""

        if self.group_type == "rg":
            self.fields['ad'].widget = forms.HiddenInput()
            self.fields['parent'].queryset = self.fields['parent'].queryset.filter(acronym="irtf")
            self.fields['parent'].initial = self.fields['parent'].queryset.first()
            self.fields['parent'].widget = forms.HiddenInput()
        else:
            self.fields['parent'].queryset = self.fields['parent'].queryset.filter(type="area")
            self.fields['parent'].label = "IETF Area"

    def clean_acronym(self):
        # Changing the acronym of an already existing group will cause 404s all
        # over the place, loose history, and generally muck up a lot of
        # things, so we don't permit it
        if self.group:
            return self.group.acronym # no change permitted

        acronym = self.cleaned_data['acronym'].strip().lower()

        if not re.match(r'^[a-z][a-z0-9]+$', acronym):
            raise forms.ValidationError("Acronym is invalid, must be at least two characters and only contain lowercase letters and numbers starting with a letter.")

        # be careful with acronyms, requiring confirmation to take existing or override historic
        existing = Group.objects.filter(acronym__iexact=acronym)
        if existing:
            existing = existing[0]

        confirmed = self.data.get("confirm_acronym", False)

        def insert_confirm_field(label, initial):
            # set required to false, we don't need it since we do the
            # validation of the field in here, and otherwise the
            # browser and Django may barf
            insert_after_in_ordered_dict(self.fields, "confirm_acronym", forms.BooleanField(label=label, required=False), after="acronym")
            # we can't set initial, it's ignored since the form is bound, instead mutate the data
            self.data = self.data.copy()
            self.data["confirm_acronym"] = initial

        if existing and existing.type_id == self.group_type:
            if existing.state_id == "bof":
                insert_confirm_field(label="Turn BoF %s into proposed %s and start chartering it" % (existing.acronym, existing.type.name), initial=True)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError("Warning: Acronym used for an existing BoF (%s)." % existing.name)
            else:
                insert_confirm_field(label="Set state of %s %s to proposed and start chartering it" % (existing.acronym, existing.type.name), initial=False)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError("Warning: Acronym used for an existing %s (%s, %s)." % (existing.type.name, existing.name, existing.state.name if existing.state else "unknown state"))

        if existing:
            raise forms.ValidationError("Acronym used for an existing group (%s)." % existing.name)

        old = GroupHistory.objects.filter(acronym__iexact=acronym, type__in=("wg", "rg"))
        if old:
            insert_confirm_field(label="Confirm reusing acronym %s" % old[0].acronym, initial=False)
            if confirmed:
                return acronym
            else:
                raise forms.ValidationError("Warning: Acronym used for a historic group.")

        return acronym

    def clean_urls(self):
        return [x.strip() for x in self.cleaned_data["urls"].splitlines() if x.strip()]

    def clean_delegates(self):
        if len(self.cleaned_data["delegates"]) > MAX_GROUP_DELEGATES:
            raise forms.ValidationError("At most %s delegates can be appointed at the same time, please remove %s delegates." % (
                    MAX_GROUP_DELEGATES, len(self.cleaned_data["delegates"]) - MAX_GROUP_DELEGATES))
        return self.cleaned_data["delegates"]


def format_urls(urls, fs="\n"):
    res = []
    for u in urls:
        if u.name:
            res.append(u"%s (%s)" % (u.url, u.name))
        else:
            res.append(u.url)
    return fs.join(res)

def get_or_create_initial_charter(group, group_type):
    charter_name = charter_name_for_group(group)

    try:
        charter = Document.objects.get(docalias__name=charter_name)
    except Document.DoesNotExist:
        charter = Document(
            name=charter_name,
            type_id="charter",
            title=group.name,
            group=group,
            abstract=group.name,
            rev="00-00",
        )
        charter.save()
        charter.set_state(State.objects.get(used=True, type="charter", slug="notrev"))

        # Create an alias as well
        DocAlias.objects.create(name=charter.name, document=charter)

    return charter

@login_required
def submit_initial_charter(request, group_type=None, acronym=None):

    # This needs refactoring.
    # The signature assumed you could have groups with the same name, but with different types, which we do not allow.
    # Consequently, this can be called with an existing group acronym and a type 
    # that doesn't match the existing group type. The code below essentially ignores the group_type argument.
    #
    # If possible, the use of get_or_create_initial_charter should be moved
    # directly into charter_submit, and this function should go away.

    if acronym==None:
        raise Http404

    group = get_object_or_404(Group, acronym=acronym)
    if not group.features.has_chartering_process:
        raise Http404

    # This is where we start ignoring the passed in group_type
    group_type = group.type_id

    if not can_manage_group(request.user, group):
        return HttpResponseForbidden("You don't have permission to access this view")

    if not group.charter:
        group.charter = get_or_create_initial_charter(group, group_type)
        group.save()

    return redirect('charter_submit', name=group.charter.name, option="initcharter")

@login_required
def edit(request, group_type=None, acronym=None, action="edit"):
    """Edit or create a group, notifying parties as
    necessary and logging changes as group events."""
    if action == "edit":
        new_group = False
    elif action in ("create","charter"):
        group = None
        new_group = True
    else:
        raise Http404

    if not new_group:
        group = get_group_or_404(acronym, group_type)
        if not group_type and group:
            group_type = group.type_id
        if not (can_manage_group(request.user, group) or group.has_role(request.user, "chair")):
            return HttpResponseForbidden("You don't have permission to access this view")

    if request.method == 'POST':
        form = GroupForm(request.POST, group=group, group_type=group_type)
        if form.is_valid():
            clean = form.cleaned_data
            if new_group:
                try:
                    group = Group.objects.get(acronym=clean["acronym"])
                    save_group_in_history(group)
                    group.time = datetime.datetime.now()
                    group.save()
                except Group.DoesNotExist:
                    group = Group.objects.create(name=clean["name"],
                                              acronym=clean["acronym"],
                                              type=GroupTypeName.objects.get(slug=group_type),
                                              state=clean["state"]
                                              )

                    if group.features.has_documents:
                        setup_default_community_list_for_group(group)

                e = ChangeStateGroupEvent(group=group, type="changed_state")
                e.time = group.time
                e.by = request.user.person
                e.state_id = clean["state"].slug
                e.desc = "Group created in state %s" % clean["state"].name
                e.save()
            else:
                save_group_in_history(group)


            if action == "charter" and not group.charter:  # make sure we have a charter
                group.charter = get_or_create_initial_charter(group, group_type)

            changes = []

            def desc(attr, new, old):
                entry = "%(attr)s changed to <b>%(new)s</b> from %(old)s"
                if new_group:
                    entry = "%(attr)s changed to <b>%(new)s</b>"

                return entry % dict(attr=attr, new=new, old=old)

            def diff(attr, name):
                v = getattr(group, attr)
                if clean[attr] != v:
                    changes.append((attr, clean[attr], desc(name, clean[attr], v)))
                    setattr(group, attr, clean[attr])

            # update the attributes, keeping track of what we're doing
            diff('name', "Name")
            diff('acronym', "Acronym")
            diff('state', "State")
            diff('parent', "IETF Area" if group.type=="wg" else "Group parent")
            diff('list_email', "Mailing list email")
            diff('list_subscribe', "Mailing list subscribe address")
            diff('list_archive', "Mailing list archive")

            personnel_change_text=""
            changed_personnel = set()
            # update roles
            for attr, slug, title in [('ad','ad','Shepherding AD'), ('chairs', 'chair', "Chairs"), ('secretaries', 'secr', "Secretaries"), ('techadv', 'techadv', "Tech Advisors"), ('delegates', 'delegate', "Delegates")]:
                new = clean[attr]
                if attr == 'ad':
                    new = [ new.role_email('ad'),] if new else []
                old = Email.objects.filter(role__group=group, role__name=slug).select_related("person")
                if set(new) != set(old):
                    changes.append((attr, new, desc(title,
                                        ", ".join(x.get_name() for x in new),
                                        ", ".join(x.get_name() for x in old))))
                    group.role_set.filter(name=slug).delete()
                    for e in new:
                        Role.objects.get_or_create(name_id=slug, email=e, group=group, person=e.person)
                    added = set(new) - set(old)
                    deleted = set(old) - set(new)
                    if added:
                        change_text=title + ' added: ' + ", ".join(x.formatted_email() for x in added)
                        personnel_change_text+=change_text+"\n"
                    if deleted:
                        change_text=title + ' deleted: ' + ", ".join(x.formatted_email() for x in deleted)
                        personnel_change_text+=change_text+"\n"
                    changed_personnel.update(set(old)^set(new))

            if personnel_change_text!="":
                email_personnel_change(request, group, personnel_change_text, changed_personnel)

            # update urls
            new_urls = clean['urls']
            old_urls = format_urls(group.groupurl_set.order_by('url'), ", ")
            if ", ".join(sorted(new_urls)) != old_urls:
                changes.append(('urls', new_urls, desc('Urls', ", ".join(sorted(new_urls)), old_urls)))
                group.groupurl_set.all().delete()
                # Add new ones
                for u in new_urls:
                    m = re.search('(?P<url>[\w\d:#@%/;$()~_?\+-=\\\.&]+)( \((?P<name>.+)\))?', u)
                    if m:
                        if m.group('name'):
                            url = GroupURL(url=m.group('url'), name=m.group('name'), group=group)
                        else:
                            url = GroupURL(url=m.group('url'), name='', group=group)
                        url.save()

            group.time = datetime.datetime.now()

            if changes and not new_group:
                for attr, new, desc in changes:
                    if attr == 'state':
                        ChangeStateGroupEvent.objects.create(group=group, time=group.time, state=new, by=request.user.person, type="changed_state", desc=desc)
                    else:
                        GroupEvent.objects.create(group=group, time=group.time, by=request.user.person, type="info_changed", desc=desc)

            group.save()

            if action=="charter":
                return redirect('charter_submit', name=group.charter.name, option="initcharter")

            return HttpResponseRedirect(group.about_url())
    else: # form.is_valid()
        if not new_group:
            ad_role = group.ad_role()
            init = dict(name=group.name,
                        acronym=group.acronym,
                        state=group.state,
                        chairs=Email.objects.filter(role__group=group, role__name="chair"),
                        secretaries=Email.objects.filter(role__group=group, role__name="secr"),
                        techadv=Email.objects.filter(role__group=group, role__name="techadv"),
                        delegates=Email.objects.filter(role__group=group, role__name="delegate"),
                        ad=ad_role and ad_role.person and ad_role.person.id,
                        parent=group.parent.id if group.parent else None,
                        list_email=group.list_email if group.list_email else None,
                        list_subscribe=group.list_subscribe if group.list_subscribe else None,
                        list_archive=group.list_archive if group.list_archive else None,
                        urls=format_urls(group.groupurl_set.all()),
                        )
        else:
            init = dict(ad=request.user.person.id if group_type == "wg" and has_role(request.user, "Area Director") else None,
                        )
        form = GroupForm(initial=init, group=group, group_type=group_type)

    return render(request, 'group/edit.html',
                  dict(group=group,
                       form=form,
                       action=action))



class ConcludeForm(forms.Form):
    instructions = forms.CharField(widget=forms.Textarea(attrs={'rows': 30}), required=True)

@login_required
def conclude(request, acronym, group_type=None):
    """Request the closing of group, prompting for instructions."""
    group = get_group_or_404(acronym, group_type)

    if not can_manage_group(request.user, group):
        return HttpResponseForbidden("You don't have permission to access this view")

    if request.method == 'POST':
        form = ConcludeForm(request.POST)
        if form.is_valid():
            instructions = form.cleaned_data['instructions']

            email_admin_re_charter(request, group, "Request closing of group", instructions, 'group_closure_requested')

            e = GroupEvent(group=group, by=request.user.person)
            e.type = "requested_close"
            e.desc = "Requested closing group"
            e.save()

            return redirect(group.features.about_page, group_type=group_type, acronym=group.acronym)
    else:
        form = ConcludeForm()

    return render(request, 'group/conclude.html', {
        'form': form,
        'group': group,
        'group_type': group_type,
    })

@login_required
def customize_workflow(request, group_type, acronym):
    group = get_group_or_404(acronym, group_type)
    if not group.features.customize_workflow:
        raise Http404

    if (not has_role(request.user, "Secretariat") and
        not group.role_set.filter(name="chair", person__user=request.user)):
        return HttpResponseForbidden("You don't have permission to access this view")

    if group_type == "rg":
        stream_id = "irtf"
        MANDATORY_STATES = ('candidat', 'active', 'rfc-edit', 'pub', 'dead')
    else:
        stream_id = "ietf"
        MANDATORY_STATES = ('c-adopt', 'wg-doc', 'sub-pub')

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "setstateactive":
            active = request.POST.get("active") == "1"
            try:
                state = State.objects.exclude(slug__in=MANDATORY_STATES).get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            if active:
                group.unused_states.remove(state)
            else:
                group.unused_states.add(state)

            # redirect so the back button works correctly, otherwise
            # repeated POSTs fills up the history
            return redirect("ietf.group.views_edit.customize_workflow", group_type=group.type_id, acronym=group.acronym)

        if action == "setnextstates":
            try:
                state = State.objects.get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            next_states = State.objects.filter(used=True, type='draft-stream-%s' % stream_id, pk__in=request.POST.getlist("next_states"))
            unused = group.unused_states.all()
            if set(next_states.exclude(pk__in=unused)) == set(state.next_states.exclude(pk__in=unused)):
                # just use the default
                group.groupstatetransitions_set.filter(state=state).delete()
            else:
                transitions, _ = GroupStateTransitions.objects.get_or_create(group=group, state=state)
                transitions.next_states = next_states

            return redirect("ietf.group.views_edit.customize_workflow", group_type=group.type_id, acronym=group.acronym)

        if action == "settagactive":
            active = request.POST.get("active") == "1"
            try:
                tag = DocTagName.objects.get(pk=request.POST.get("tag"))
            except DocTagName.DoesNotExist:
                return HttpResponse("Invalid tag %s" % request.POST.get("tag"))

            if active:
                group.unused_tags.remove(tag)
            else:
                group.unused_tags.add(tag)

            return redirect("ietf.group.views_edit.customize_workflow", group_type=group.type_id, acronym=group.acronym)

    # put some info for the template on tags and states
    unused_tags = group.unused_tags.all().values_list('slug', flat=True)
    tags = DocTagName.objects.filter(slug__in=get_tags_for_stream_id(stream_id))
    for t in tags:
        t.used = t.slug not in unused_tags

    unused_states = group.unused_states.all().values_list('slug', flat=True)
    states = State.objects.filter(used=True, type="draft-stream-%s" % stream_id)
    transitions = dict((o.state, o) for o in group.groupstatetransitions_set.all())
    for s in states:
        s.used = s.slug not in unused_states
        s.mandatory = s.slug in MANDATORY_STATES

        default_n = s.next_states.all()
        if s in transitions:
            n = transitions[s].next_states.all()
        else:
            n = default_n

        s.next_states_checkboxes = [(x in n, x in default_n, x) for x in states]
        s.used_next_states = [x for x in n if x.slug not in unused_states]

    return render(request, 'group/customize_workflow.html', {
            'group': group,
            'states': states,
            'tags': tags,
            })
