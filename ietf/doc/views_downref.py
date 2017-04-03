import re
import datetime
import debug                            # pyflakes:ignore

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse as urlreverse
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, HttpResponse, HttpResponseRedirect, QueryDict
from ietf.ietfauth.utils import has_role, role_required
from django.shortcuts import render

from ietf.doc.models import ( Document, RelatedDocument, DocAlias, State, DocEvent )
from ietf.doc.fields import select2_id_doc_name_json
from ietf.doc.utils import get_search_cache_key
from ietf.group.models import Group
from ietf.idindex.index import active_drafts_index_by_group
from ietf.name.models import DocTagName, DocTypeName, StreamName
from ietf.person.models import Person
from ietf.utils.draft_search import normalize_draftname
from ietf.doc.utils_search import prepare_document_table
from ietf.doc.fields import SearchableDocAliasesField, SearchableDocAliasField
from ietf.doc.forms import AddDownrefForm


def downref_registry(request):
    title = "Downref registry"
    add_button = has_role(request.user, "Area Director") or has_role(request.user, "Secretariat")
    
    downref_doc_pairs = [ ]
    downref_relations = RelatedDocument.objects.filter(relationship_id='downrefappr')
    for rel in downref_relations:
        downref_doc_pairs.append((rel.target.document, rel.source))

    return render(request, 'doc/downref.html', {
             "doc_pairs": downref_doc_pairs,
             "title": title,
             "add_button": add_button,
             })


@role_required("Area Director", "Secretariat")
def downref_registry_add(request):
    title = "Add entry to the downref registry"
    login = request.user.person

    if request.method == 'POST':
        form = AddDownrefForm(request.POST)
        if form.is_valid():
            drafts = form.cleaned_data['drafts']
            rfc = form.cleaned_data['rfc']
            for da in drafts:
                RelatedDocument.objects.create(source=da.document,
                        target=rfc, relationship_id='downrefappr')
                c = DocEvent(type="downref_approved", doc=da.document,
                        rev=da.document.rev, by=login)
                c.desc = "Downref to RFC %s approved by Last Call for %s-%s" % (
                        rfc.document.rfc_number(), da.name, da.document.rev)
                c.save()
                c = DocEvent(type="downref_approved", doc=rfc.document,
                        rev=rfc.document.rev, by=login)
                c.desc = "Downref to RFC %s approved by Last Call for %s-%s" % (
                        rfc.document.rfc_number(), da.name, da.document.rev)
                c.save()

            return HttpResponseRedirect(urlreverse('ietf.doc.views_downref.downref_registry'))
    else:
        form = AddDownrefForm()

    return render(request, 'doc/downref_add.html', {
             "title": title,
             "add_downref_form": form,
             })
