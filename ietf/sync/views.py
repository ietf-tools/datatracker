import subprocess, os, json

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseServerError, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django.conf import settings
from django import forms
from django.db.models import Q
from django.contrib.auth.models import User

from ietf.ietfauth.decorators import role_required, has_role
from ietf.doc.models import *
from ietf.sync import iana, rfceditor
from ietf.sync.discrepancies import find_discrepancies
from ietf.utils.serialize import object_as_shallow_dict

SYNC_BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../bin"))

#@role_required('Secretariat', 'IANA', 'RFC Editor')
def discrepancies(request):
    sections = find_discrepancies()

    return render_to_response("sync/discrepancies.html",
                              dict(sections=sections),
                              context_instance=RequestContext(request))

def notify(request, org, notification):
    """Notify that something has changed at another site to trigger a
    run of one of the sync scripts."""

    known_orgs = {
        "iana": "IANA",
        "rfceditor": "RFC Editor",
        }

    if org not in known_orgs:
        raise Http404

    # handle auth, to make it easier for the other end, you can send
    # the username/password as POST parameters instead of having to
    # visit the login page
    user = request.user

    username = request.POST.get("username") or request.GET.get("username")
    password = request.POST.get("password") or request.GET.get("password")

    if username != None and password != None:
        if settings.SERVER_MODE == "production" and not request.is_secure():
            return HttpResponseForbidden("You must use HTTPS when sending username/password")

        if not user.is_authenticated():
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return HttpResponse("Invalid username/password")

            if not user.check_password(password):
                return HttpResponse("Invalid username/password")

    if not has_role(user, ("Secretariat", known_orgs[org])):
        return HttpResponseForbidden("You do not have the necessary permissions to view this page")

    known_notifications = {
        "protocols": "an added reference to an RFC at <a href=\"%s\">the IANA protocols page</a>" % iana.PROTOCOLS_URL,
        "changes": "new changes at <a href=\"%s\">the changes JSON dump</a>" % iana.CHANGES_URL,
        "queue": "new changes to <a href=\"%s\">queue2.xml</a>" % rfceditor.QUEUE_URL,
        "index": "new changes to <a href=\"%s\">rfc-index.xml</a>" % rfceditor.INDEX_URL,
        }

    if notification not in known_notifications:
        raise Http404

    if request.method == "POST":
        def runscript(name):
            p = subprocess.Popen(["python", os.path.join(SYNC_BIN_PATH, name)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, _ = p.communicate()
            return (p.returncode, out)

        if notification == "protocols":
            failed, out = runscript("iana-protocols-updates")

        if notification == "changes":
            failed, out = runscript("iana-changes-updates")

        if notification == "queue":
            failed, out = runscript("rfc-editor-queue-updates")

        if notification == "index":
            failed, out = runscript("rfc-editor-index-updates")

        if failed:
            return HttpResponseServerError("FAIL\n\n" + out, content_type="text/plain")
        else:
            return HttpResponse("OK", content_type="text/plain")

    return render_to_response('sync/notify.html',
                              dict(org=known_orgs[org],
                                   notification=notification,
                                   help_text=known_notifications[notification],
                                   ),
                              context_instance=RequestContext(request))

@role_required('Secretariat', 'RFC Editor')
def rfceditor_undo(request):
    """Undo a DocEvent."""
    events = StateDocEvent.objects.filter(state_type="draft-rfceditor",
                                          time__gte=datetime.datetime.now() - datetime.timedelta(weeks=1)
                                          ).order_by("-time", "-id")

    if request.method == "POST":
        try:
            eid = int(request.POST.get("event", ""))
        except ValueError:
            return HttpResponse("Could not parse event id")

        try:
            e = events.get(id=eid)
        except StateDocEvent.DoesNotExist:
            return HttpResponse("Event does not exist")

        doc = e.doc

        # possibly reset the state of the document
        all_events = StateDocEvent.objects.filter(doc=doc, state_type="draft-rfceditor").order_by("-time", "-id")
        if all_events and all_events[0] == e:
            if len(all_events) > 1:
                doc.set_state(all_events[1].state)
            else:
                doc.unset_state("draft-rfceditor")

        dump = DeletedEvent()
        dump.content_type = ContentType.objects.get_for_model(type(e))
        dump.json = json.dumps(object_as_shallow_dict(e), indent=2)
        dump.by = request.user.person
        dump.save()

        e.delete()

        return HttpResponseRedirect(urlreverse("ietf.sync.views.rfceditor_undo"))

    return render_to_response('sync/rfceditor_undo.html',
                              dict(events=events,
                                   ),
                              context_instance=RequestContext(request))
