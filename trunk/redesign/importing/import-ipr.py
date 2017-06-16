#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False
settings.IMPORTING_IPR = True

from django.core import management
management.setup_environ(settings)

from ietf.ipr.models import IprDraftOld, IprRfcOld, IprDocAlias, IprDetail
from ietf.doc.models import DocAlias

# imports IprDraft and IprRfc, converting them to IprDocAlias links to Document

# assumptions: documents have been imported

# some links are borked, only import those that reference an existing IprDetail
ipr_ids = IprDetail.objects.all()

for o in IprDraftOld.objects.filter(ipr__in=ipr_ids).select_related("document").order_by("id").iterator():
    try:
        alias = DocAlias.objects.get(name=o.document.filename)
    except DocAlias.DoesNotExist:
        print "COULDN'T FIND DOCUMENT", o.document.filename
        continue
    
    try:
        IprDocAlias.objects.get(ipr=o.ipr_id, doc_alias=alias)
    except IprDocAlias.DoesNotExist:
        link = IprDocAlias()
        link.ipr_id = o.ipr_id
        link.doc_alias = alias
        link.rev = o.revision or ""
        link.save()
        
    print "importing IprDraft", o.pk, "linking", o.ipr_id, o.document.filename

for o in IprRfcOld.objects.filter(ipr__in=ipr_ids).select_related("document").order_by("id").iterator():
    try:
        alias = DocAlias.objects.get(name="rfc%s" % o.document.rfc_number)
    except DocAlias.DoesNotExist:
        print "COULDN'T FIND RFC%s", o.document.rfc_number
        continue
    
    try:
        IprDocAlias.objects.get(ipr=o.ipr_id, doc_alias=alias)
    except IprDocAlias.DoesNotExist:
        link = IprDocAlias()
        link.ipr_id = o.ipr_id
        link.doc_alias = alias
        link.rev = ""
        link.save()
        
    print "importing IprRfc", o.pk, "linking", o.ipr_id, o.document.rfc_number
