# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse as urlreverse
from django.http import HttpResponseRedirect
from django.shortcuts import render

import debug                            # pyflakes:ignore

from ietf.doc.models import ( RelatedDocument, DocEvent )
from ietf.doc.forms import AddDownrefForm
from ietf.ietfauth.utils import has_role, role_required

def downref_registry(request):
    title = "Downref registry"
    add_button = has_role(request.user, "Area Director") or has_role(request.user, "Secretariat")
    
    downref_doc_pairs = [ ]
    downref_relations = RelatedDocument.objects.filter(relationship_id='downref-approval')
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
                        target=rfc, relationship_id='downref-approval')
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
