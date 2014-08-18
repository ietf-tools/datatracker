# Copyright The IETF Trust 2008, All Rights Reserved

from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.http import Http404, HttpResponseForbidden
from django import forms

from ietf.doc.views_search import SearchForm, retrieve_search_results
from ietf.group.models import Group, GroupEvent, Role
from ietf.group.utils import save_group_in_history
from ietf.ietfauth.utils import has_role
from ietf.name.models import StreamName
from ietf.person.fields import AutocompletedEmailsField
from ietf.person.models import Email

import debug                            # pyflakes:ignore

def streams(request):
    streams = [ s.slug for s in StreamName.objects.all().exclude(slug__in=['ietf', 'legacy']) ]
    streams = Group.objects.filter(acronym__in=streams)
    return render_to_response('group/index.html', {'streams':streams}, context_instance=RequestContext(request))

def stream_documents(request, acronym):
    streams = [ s.slug for s in StreamName.objects.all().exclude(slug__in=['ietf', 'legacy']) ]
    if not acronym in streams:
        raise Http404("No such stream: %s" % acronym)
    stream = StreamName.objects.get(slug=acronym)
    form = SearchForm({'by':'stream', 'stream':acronym,
                       'rfcs':'on', 'activedrafts':'on'})
    docs, meta = retrieve_search_results(form)
    return render_to_response('group/stream_documents.html', {'stream':stream, 'docs':docs, 'meta':meta }, context_instance=RequestContext(request))

class StreamEditForm(forms.Form):
    delegates = AutocompletedEmailsField(required=False, only_users=True)

def stream_edit(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)

    if not (has_role(request.user, "Secretariat") or group.has_role(request.user, "chair")):
        return HttpResponseForbidden("You don't have permission to access this page.")

    chairs = Email.objects.filter(role__group=group, role__name="chair").select_related("person")

    if request.method == 'POST':
        form = StreamEditForm(request.POST)

        if form.is_valid():
            save_group_in_history(group)

            # update roles
            attr, slug, title = ('delegates', 'delegate', "Delegates")

            new = form.cleaned_data[attr]
            old = Email.objects.filter(role__group=group, role__name=slug).select_related("person")
            if set(new) != set(old):
                desc = "%s changed to <b>%s</b> from %s" % (
                    title, ", ".join(x.get_name() for x in new), ", ".join(x.get_name() for x in old))

                GroupEvent.objects.create(group=group, by=request.user.person, type="info_changed", desc=desc)

                group.role_set.filter(name=slug).delete()
                for e in new:
                    Role.objects.get_or_create(name_id=slug, email=e, group=group, person=e.person)

            return redirect("ietf.group.views.streams")
    else:
        form = StreamEditForm(initial=dict(delegates=Email.objects.filter(role__group=group, role__name="delegate")))

    return render_to_response('group/stream_edit.html',
                              {'group': group,
                               'chairs': chairs,
                               'form': form,
                               },
                              context_instance=RequestContext(request))
    
