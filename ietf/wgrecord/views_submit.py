# Copyright The IETF Trust 2011, All Rights Reserved
import os

from datetime import datetime
from django.http import HttpResponseRedirect, Http404
from django import forms
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.template import RequestContext

from ietf.ietfauth.decorators import group_required
from django.core.exceptions import ObjectDoesNotExist
from group.models import Group, save_group_in_history
from doc.models import Document, DocHistory, DocEvent

from django.conf import settings
from utils import next_revision, set_or_create_charter, save_charter_in_history

class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Charter text", help_text="Edit the charter text", required=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def save(self, wg, rev):
        fd = self.cleaned_data['txt']
        filename = os.path.join(settings.CHARTER_PATH, 'charter-ietf-%s-%s.txt' % (wg.acronym, rev))
        if fd:
            # A file was specified. Save it.
            destination = open(filename, 'wb+')
            for chunk in fd.chunks():
                destination.write(chunk)
            destination.close()
        else:
            # No file, save content
            destination = open(filename, 'wb+')
            content = self.cleaned_data['content']
            destination.write(content)
            destination.close()

@group_required('Area_Director','Secretariat')
def submit(request, name):
    # Get WG by acronym, redirecting if there's a newer acronym
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('charter_submit', name=wglist[0].group.acronym)
        else:
            raise Http404
    # Get charter
    charter = set_or_create_charter(wg)
    
    login = request.user.get_profile()

    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            save_charter_in_history(charter)
            # Also save group history so we can search for it
            save_group_in_history(wg)

            charter.rev = next_revision(charter.rev)

            e = DocEvent()
            e.type = "new_revision"
            e.by = login
            e.doc = charter
            e.desc = "New version available: <b>charter-ietf-%s-%s.txt</b>" % (wg.acronym, charter.rev)
            e.save()
            
            # Save file on disk
            form.save(wg, charter.rev)

            charter.time = datetime.now()
            charter.save()

            return HttpResponseRedirect(reverse('wg_view_record', kwargs={'name': wg.acronym}))
    else:
        filename = os.path.join(settings.CHARTER_PATH, 'charter-ietf-%s-%s.txt' % (wg.acronym, wg.charter.rev))
        try:
            charter_text = open(filename, 'r')
            init = dict(content = charter_text.read())
        except IOError:
            init = {}
        form = UploadForm(initial = init)
    return render_to_response('wgrecord/submit.html',
                              {'form': form,
                               'next_rev': next_revision(wg.charter.rev),
                               'wg': wg},
                              context_instance=RequestContext(request))
