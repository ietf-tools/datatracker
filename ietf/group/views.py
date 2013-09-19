# Copyright The IETF Trust 2008, All Rights Reserved

from django.shortcuts import render_to_response
from django.template import RequestContext, loader
from django.http import Http404, HttpResponse

from ietf.group.models import Group
from ietf.doc.models import Document
from ietf.doc.views_search import SearchForm, retrieve_search_results
from ietf.name.models import StreamName

import debug

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

    