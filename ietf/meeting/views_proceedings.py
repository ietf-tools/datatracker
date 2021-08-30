# Copyright The IETF Trust 2021 All Rights Reserved
from pathlib import Path

from django import forms
from django.http import Http404, FileResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404

import debug                            # pyflakes:ignore

from ietf.doc.utils import add_state_change_event
from ietf.doc.models import DocAlias, DocEvent, Document, NewRevisionDocEvent, State
from ietf.ietfauth.utils import role_required
from ietf.meeting.forms import FileUploadForm
from ietf.meeting.models import Meeting, MeetingHost
from ietf.meeting.helpers import get_meeting
from ietf.name.models import ProceedingsMaterialTypeName
from ietf.secr.proceedings.utils import handle_upload_file
from ietf.utils.text import xslugify

class UploadProceedingsMaterialForm(FileUploadForm):
    use_url = forms.BooleanField(
        required=False,
        label='Use an external URL instead of uploading a document',
    )
    external_url = forms.URLField(
        required=False,
        help_text='External URL to link from the proceedings'
    )
    field_order = ['use_url', 'external_url']  # will precede superclass fields

    class Media:
        js = (
            'ietf/js/upload-material.js',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(doc_type='procmaterials', *args, **kwargs)
        self.fields['file'].label = 'Select a file to upload. Allowed format{}: {}'.format(
            '' if len(self.mime_types) == 1 else 's',
            ', '.join(self.mime_types),
        )
        self.fields['file'].required = False

    def clean_file(self):
        if self.cleaned_data.get('file', None) is None:
            return None  # bypass cleaning the file if none was provided
        return super().clean_file()

    def clean(self):
        if self.cleaned_data['use_url']:
            if not self.cleaned_data['external_url']:
                self.add_error('external_url', 'This field is required')
        else:
            self.cleaned_data['external_url'] = None  # make sure this is empty
            if self.cleaned_data['file'] is None:
                self.add_error('file', 'This field is required')

class EditProceedingsMaterialForm(forms.Form):
    """Form to edit proceedings material properties"""
    # A note: we use Document._meta to get the max length of a model field.
    # The leading underscore makes this look like accessing a private member,
    # but it is in fact part of Django's API.
    # noinspection PyProtectedMember
    title = forms.CharField(
        help_text='Label that will appear on the proceedings page',
        max_length=Document._meta.get_field("title").max_length,
        required=True,
    )


def save_proceedings_material_doc(meeting, material_type, title, request, file=None, external_url=None, state=None):
    events = []
    by = request.user.person

    if not (file is None or external_url is None):
        raise ValueError('One of file or external_url must be None')

    # doc naming duplicates naming of docs elsewhere - use dashes instead of underscores
    doc_name = '-'.join([
        'proceedings',
        meeting.number,
        xslugify(
            getattr(material_type, 'slug', material_type)
        ).replace('_', '-')[:128],
    ])

    created = False
    doc = Document.objects.filter(type_id='procmaterials', name=doc_name).first()
    if doc is None:
        if file is None and external_url is None:
            raise ValueError('Cannot create a new document without a file or external URL')
        doc = Document.objects.create(
            type_id='procmaterials',
            name=doc_name,
            rev="00",
        )
        created = True

    # do this even if we did not create the document, just to be sure the alias exists
    alias, _ = DocAlias.objects.get_or_create(name=doc.name)
    alias.docs.add(doc)

    if file:
        if not created:
            doc.rev = '{:02}'.format(int(doc.rev) + 1)
        filename = f'{doc.name}-{doc.rev}{Path(file.name).suffix}'
        save_error = handle_upload_file(file, filename, meeting, 'procmaterials', )
        if save_error is not None:
            raise RuntimeError(save_error)

        doc.uploaded_filename = filename
        doc.external_url = ''
        e = NewRevisionDocEvent.objects.create(
            type="new_revision",
            doc=doc,
            rev=doc.rev,
            by=by,
            desc="New version available: <b>%s-%s</b>" % (doc.name, doc.rev),
        )
        events.append(e)
    elif (external_url is not None) and external_url != doc.external_url:
        if not created:
            doc.rev = '{:02}'.format(int(doc.rev) + 1)
        doc.uploaded_filename = ''
        doc.external_url = external_url
        e = NewRevisionDocEvent.objects.create(
            type="new_revision",
            doc=doc,
            rev=doc.rev,
            by=by,
            desc="Set external URL to <b>{}</b>".format(external_url),
        )
        events.append(e)

    if doc.title != title and title is not None:
        e = DocEvent(doc=doc, rev=doc.rev, by=by, type='changed_document')
        e.desc = f'Changed title to <b>{title}</b>'
        if doc.title:
            e.desc += f' from {doc.title}'
        e.save()
        events.append(e)
        doc.title = title

    # Set the state and create a change event if necessary
    prev_state = doc.get_state('procmaterials')
    new_state = state if state is not None else State.objects.get(type_id='procmaterials', slug='active')
    if prev_state != new_state:
        if not created:
            e = add_state_change_event(doc, by, prev_state, new_state)
            events.append(e)
        doc.set_state(new_state)

    if events:
        doc.save_with_history(events)

    return doc


@role_required('Secretariat')
def upload_material(request, num, material_type):
    meeting = get_meeting(num)

    # turn the material_type slug into the actual instance
    material_type = get_object_or_404(ProceedingsMaterialTypeName, slug=material_type)
    material = meeting.proceedings_materials.filter(type=material_type).first()

    if request.method == 'POST':
        form = UploadProceedingsMaterialForm(request.POST, request.FILES)

        if form.is_valid():
            doc = save_proceedings_material_doc(
                meeting,
                material_type,
                request=request,
                file=form.cleaned_data.get('file', None),
                external_url=form.cleaned_data.get('external_url', None),
                title=str(material if material is not None else material_type),
            )
            if material is None:
                meeting.proceedings_materials.create(type=material_type, document=doc)
            return redirect('ietf.meeting.views_proceedings.material_details', num=num)
    else:
        initial = dict()
        if material is not None:
            ext_url = material.document.external_url
            if ext_url != '':
                initial['use_url'] = True
                initial['external_url'] = ext_url
        form = UploadProceedingsMaterialForm(initial=initial)

    return render(request, 'meeting/proceedings/upload_material.html', {
        'form': form,
        'material': material,
        'material_type': material_type,
        'meeting': meeting,
        'submit_button_label': 'Upload',
    })

@role_required('Secretariat')
def material_details(request, num):
    meeting = get_meeting(num)
    proceedings_materials = [
        (type_name, meeting.proceedings_materials.filter(type=type_name).first())
        for type_name in ProceedingsMaterialTypeName.objects.all()
    ]
    return render(
        request,
        'meeting/proceedings/material_details.html',
        dict(
            meeting=meeting,
            proceedings_materials=proceedings_materials,
        )
    )

@role_required('Secretariat')
def edit_material(request, num, material_type):
    meeting = get_meeting(num)
    material = meeting.proceedings_materials.filter(type_id=material_type).first()
    if material is None:
        raise Http404('No such material for this meeting')
    if request.method == 'POST':
        form = EditProceedingsMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            save_proceedings_material_doc(
                meeting,
                material_type,
                request=request,
                title=form.cleaned_data['title'],
            )
            return redirect("ietf.meeting.views_proceedings.material_details", num=meeting.number)
    else:
        form = EditProceedingsMaterialForm(
            initial=dict(
                title=material.document.title,
            ),
        )

    return render(request, 'meeting/proceedings/edit_material.html', {
        'form': form,
        'material': material,
        'material_type': material.type,
        'meeting': meeting,
    })

@role_required('Secretariat')
def remove_restore_material(request, num, material_type, action):
    """Remove or restore proceedings material"""
    if action not in ['remove', 'restore']:
        return HttpResponseBadRequest('Unsupported action')
    meeting = get_meeting(num)
    material = meeting.proceedings_materials.filter(type_id=material_type).first()
    if material is None:
        raise Http404('No such material for this meeting')
    if request.method == 'POST':
        prev_state = material.document.get_state('procmaterials')
        new_state = State.objects.get(
            type_id='procmaterials',
            slug='active' if action == 'restore' else 'removed',
        )
        if new_state != prev_state:
            material.document.set_state(new_state)
            add_state_change_event(material.document, request.user.person, prev_state, new_state)
        return redirect('ietf.meeting.views_proceedings.material_details', num=num)

    return render(
        request,
        'meeting/proceedings/remove_restore_material.html',
        dict(material=material, action=action)
    )

@role_required('Secretariat')
def edit_meetinghosts(request, num):
    meeting = get_meeting(num)

    MeetingHostFormSet = forms.inlineformset_factory(
        Meeting,
        MeetingHost,
        fields=('name', 'logo',),
        extra=2,
    )

    if request.method == 'POST':
        formset = MeetingHostFormSet(request.POST, request.FILES, instance=meeting)
        if formset.is_valid():
            # If we are removing a MeetingHost or replacing its logo, delete the
            # old logo file.
            for form in formset:
                if form.instance.pk:
                    deleted = form.cleaned_data.get('DELETE', False)
                    logo_replaced = 'logo' in form.changed_data
                    if deleted or logo_replaced:
                        orig_instance = meeting.meetinghosts.get(pk=form.instance.pk)
                        orig_instance.logo.delete()

            # this will update the DB and add any newly uploaded files
            formset.save()
            return redirect('ietf.meeting.views.materials', num=meeting.number)
    else:
        formset = MeetingHostFormSet(instance=meeting)

    return render(request, 'meeting/proceedings/edit_meetinghosts.html', {
        'formset': formset,
        'meeting': meeting,
    })


def meetinghost_logo(request, num, host_id):
    host = get_object_or_404(MeetingHost, pk=host_id)
    if host.meeting.number != num:
        raise Http404()

    return FileResponse(host.logo.open())
