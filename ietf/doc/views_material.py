# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# views for managing group materials (slides, ...)
import io
import os
import re

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.html import mark_safe # type:ignore
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, DocTypeName, DocEvent, State
from ietf.doc.models import NewRevisionDocEvent
from ietf.doc.utils import add_state_change_event, check_common_doc_name_rules
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.utils.response import permission_denied

@login_required
def choose_material_type(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    if not group.features.has_nonsession_materials:
        raise Http404

    return render(request, 'doc/material/choose_material_type.html', {
        'group': group,
        'material_types': DocTypeName.objects.filter(slug__in=group.features.material_types),
    })

class UploadMaterialForm(forms.Form):
    title = forms.CharField(max_length=Document._meta.get_field("title").max_length)
    name = forms.CharField(max_length=Document._meta.get_field("name").max_length)
    abstract = forms.CharField(max_length=Document._meta.get_field("abstract").max_length,widget=forms.Textarea, strip=False)
    state = forms.ModelChoiceField(State.objects.all(), empty_label=None)
    material = forms.FileField(label='File')

    def __init__(self, doc_type, action, group, doc, *args, **kwargs):
        super(UploadMaterialForm, self).__init__(*args, **kwargs)

        self.fields["state"].queryset = self.fields["state"].queryset.filter(type__slug=doc_type.slug)

        self.doc_type = doc_type
        self.action = action
        self.group = group

        if action == "new":
            self.fields["state"].widget = forms.HiddenInput()
            self.fields["state"].queryset = self.fields["state"].queryset.filter(slug="active")
            self.fields["state"].initial = self.fields["state"].queryset[0].pk
            self.fields["name"].initial = self._default_name()
        else:
            del self.fields["name"]

            self.fields["title"].initial = doc.title
            self.fields["abstract"].initial = doc.abstract
            self.fields["state"].initial = doc.get_state().pk if doc.get_state() else None
            if doc.get_state_slug() == "deleted":
                self.fields["state"].help_text = "Note: If you wish to revise this document, you may wish to change the state so it's not deleted."

            if action in ["title","state","abstract"]:
                for fieldname in ["title","state","material","abstract"]: 
                    if fieldname != action:
                        del self.fields[fieldname]

        if doc_type.slug == 'procmaterials' and 'abstract' in self.fields:
            del self.fields['abstract']

    def _default_name(self):
        return "%s-%s-" % (self.doc_type.slug, self.group.acronym)

    def clean_name(self):
        name = self.cleaned_data["name"].strip().rstrip("-")

        check_common_doc_name_rules(name)

        if not re.search("^%s-%s-[a-z0-9]+" % (self.doc_type.slug, self.group.acronym), name):
            raise forms.ValidationError("The name must start with %s-%s- followed by descriptive dash-separated words." % (self.doc_type.slug, self.group.acronym))

        existing = Document.objects.filter(type=self.doc_type, name=name)
        if existing:
            url = urlreverse('ietf.doc.views_material.edit_material', kwargs={ 'name': existing[0].name, 'action': 'revise' })
            raise forms.ValidationError(mark_safe("Can't upload: %s with name %s already exists. Choose another title and name for what you're uploading or <a href=\"%s\">revise the existing %s</a>." % (self.doc_type.name, name, url, name)))

        return name

@login_required
def edit_material(request, name=None, acronym=None, action=None, doc_type=None):
    # the materials process is not very developed, so at the moment we
    # handle everything through the same view/form

    if action == "new":
        group = get_object_or_404(Group, acronym=acronym)
        if not group.features.has_nonsession_materials:
            raise Http404

        doc = None
        document_type = get_object_or_404(DocTypeName, slug=doc_type)
    else:
        doc = get_object_or_404(Document, name=name)
        group = doc.group
        document_type = doc.type

    valid_doctypes = ['procmaterials']
    if group is not None:
        valid_doctypes.extend(['minutes','agenda','bluesheets'])
        valid_doctypes.extend(group.features.material_types)

    if document_type.slug not in valid_doctypes:
        raise Http404

    if not can_manage_materials(request.user, group):
        permission_denied(request, "You don't have permission to access this view")

    if request.method == 'POST':
        form = UploadMaterialForm(document_type, action, group, doc, request.POST, request.FILES)

        if form.is_valid():
            events = []

            if action == "new":
                doc = Document.objects.create(
                    type=document_type,
                    group=group,
                    rev="00",
                    name=form.cleaned_data["name"])

                prev_rev = None
            else:
                prev_rev = doc.rev

            prev_title = doc.title
            prev_state = doc.get_state()
            prev_abstract = doc.abstract

            if "title" in form.cleaned_data:
                doc.title = form.cleaned_data["title"]

            if "abstract" in form.cleaned_data:
                doc.abstract = form.cleaned_data["abstract"]

            if "material" in form.fields:
                if action != "new":
                    doc.rev = "%02d" % (int(doc.rev) + 1)

                f = form.cleaned_data["material"]
                file_ext = os.path.splitext(f.name)[1]

                with io.open(os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + file_ext), 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)

            if action == "new":
                alias, __ = DocAlias.objects.get_or_create(name=doc.name)
                alias.docs.add(doc)

            if prev_rev != doc.rev:
                e = NewRevisionDocEvent(type="new_revision", doc=doc, rev=doc.rev)
                e.by = request.user.person
                e.desc = "New version available: <b>%s-%s</b>" % (doc.name, doc.rev)
                e.save()
                events.append(e)

            if prev_title != doc.title:
                e = DocEvent(doc=doc, rev=doc.rev, by=request.user.person, type='changed_document')
                e.desc = "Changed title to <b>%s</b>" % doc.title
                if prev_title:
                    e.desc += " from %s" % prev_title
                e.save()
                events.append(e)

            if prev_abstract != doc.abstract:
                e = DocEvent(doc=doc, rev=doc.rev, by=request.user.person, type='changed_document')
                e.desc = "Changed abstract to <b>%s</b>" % doc.abstract
                if prev_abstract:
                    e.desc += " from %s" % prev_abstract
                e.save()
                events.append(e)

            if "state" in form.cleaned_data and form.cleaned_data["state"] != prev_state:
                doc.set_state(form.cleaned_data["state"])
                e = add_state_change_event(doc, request.user.person, prev_state, form.cleaned_data["state"])
                events.append(e)

            if events:
                doc.save_with_history(events)

            return redirect("ietf.doc.views_doc.document_main", name=doc.name)
    else:
        form = UploadMaterialForm(document_type, action, group, doc)

    # decide where to go if upload is canceled
    if doc:
        back_href = urlreverse('ietf.doc.views_doc.document_main', kwargs={'name': doc.name})
    else:
        back_href = urlreverse('ietf.group.views.materials', kwargs={'acronym': group.acronym})

    if document_type.slug == 'procmaterials':
        name_prefix = 'proceedings-'
    else:
        name_prefix = f'{document_type.slug}-{group.acronym}-'

    return render(request, 'doc/material/edit_material.html', {
        'group': group,
        'form': form,
        'action': action,
        'material_type': document_type,
        'name_prefix': name_prefix,
        'doc': doc,
        'doc_name': doc.name if doc else "",
        'back_href': back_href,
    })


