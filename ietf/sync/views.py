import subprocess, os

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django import forms
from django.db.models import Q

from ietf.ietfauth.decorators import role_required
from ietf.doc.models import *
from ietf.sync import iana, rfceditor
from ietf.sync.discrepancies import find_discrepancies

SYNC_BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../bin"))

#@role_required('Secretariat', 'IANA', 'RFC Editor')
def discrepancies(request):
    sections = find_discrepancies()

    return render_to_response("sync/discrepancies.html",
                              dict(sections=sections),
                              context_instance=RequestContext(request))


class UpdateIanaForm(forms.Form):
    protocols_page = forms.BooleanField(initial=False, required=False, help_text="For when a reference to an RFC has been added to <a href=\"%s\">the IANA protocols page</a>" % iana.PROTOCOLS_URL)
    changes = forms.BooleanField(initial=False, required=False, help_text="For new changes at <a href=\"%s\">the changes JSON dump</a>" % iana.CHANGES_URL)

def update_iana(request):
    if request.method == 'POST':
        form = UpdateIanaForm(request.POST)
        if form.is_valid():
            failed = False
            if form.cleaned_data["protocols_page"]:
                failed = failed or subprocess.call(["python", os.path.join(SYNC_BIN_PATH, "iana-protocols-updates")])
            if form.cleaned_data["changes"]:
                failed = failed or subprocess.call(["python", os.path.join(SYNC_BIN_PATH, "iana-changes-updates")])

            if failed:
                return HttpResponse("FAIL")
            else:
                return HttpResponse("OK")
    else:
        form = UpdateIanaForm()

    return render_to_response('sync/update.html',
                              dict(form=form,
                                   org="IANA",
                                   ),
                              context_instance=RequestContext(request))


class UpdateRFCEditorForm(forms.Form):
    queue = forms.BooleanField(initial=False, required=False, help_text="For when <a href=\"%s\">queue2.xml</a> has been updated" % rfceditor.QUEUE_URL)
    index = forms.BooleanField(initial=False, required=False, help_text="For when <a href=\"%s\">rfc-index.xml</a> has been updated" % rfceditor.INDEX_URL)

def update_rfc_editor(request):
    if request.method == 'POST':
        form = UpdateRFCEditorForm(request.POST)
        if form.is_valid():
            failed = False
            if form.cleaned_data["queue"]:
                failed = failed or subprocess.call(["python", os.path.join(SYNC_BIN_PATH, "rfc-editor-queue-updates")])
            if form.cleaned_data["index"]:
                failed = failed or subprocess.call(["python", os.path.join(SYNC_BIN_PATH, "rfc-editor-index-updates")])

            if failed:
                return HttpResponse("FAIL")
            else:
                return HttpResponse("OK")
    else:
        form = UpdateRFCEditorForm()

    return render_to_response('sync/update.html',
                              dict(form=form,
                                   org="RFC Editor",
                                   ),
                              context_instance=RequestContext(request))
