# Copyright The IETF Trust 2007, All Rights Reserved

import codecs
import re
import os.path
import django.utils.html
from django.shortcuts import render_to_response as render
from django.template import RequestContext
from django.conf import settings
from django.http import Http404
from ietf.idtracker.models import IETFWG, InternetDraft, Rfc
from ietf.ipr.models import IprRfc, IprDraft, IprDetail
from ietf.ipr.related import related_docs
from ietf.utils import log, normalize_draftname


def mark_last_doc(iprs):
    for item in iprs:
        docs = item.docs()
        count = len(docs)
        if count > 1:
            item.last_draft = docs[count-1]

def iprs_from_docs(docs):
    iprs = []
    for doc in docs:
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            from ietf.ipr.models import IprDocAlias
            disclosures = [ x.ipr for x in IprDocAlias.objects.filter(doc_alias=doc, ipr__status__in=[1,3]) ]
            
        elif isinstance(doc, InternetDraft):
            disclosures = [ item.ipr for item in IprDraft.objects.filter(document=doc, ipr__status__in=[1,3]) ]
        elif isinstance(doc, Rfc):
            disclosures = [ item.ipr for item in IprRfc.objects.filter(document=doc, ipr__status__in=[1,3]) ]
        else:
            raise ValueError("Doc type is neither draft nor rfc: %s" % doc)
        if disclosures:
            doc.iprs = disclosures
            iprs += disclosures
    iprs = list(set(iprs))
    return iprs, docs

def patent_file_search(url, q):
    if url:
        fname = url.split("/")[-1]
        fpath = os.path.join(settings.IPR_DOCUMENT_PATH, fname)
        #print "*** Checking file", fpath
        if os.path.isfile(fpath):
            #print "*** Found file", fpath            
            file = codecs.open(fpath, mode='r', encoding='utf-8', errors='replace')
            text = file.read()
            file.close
            return q in text
    return False

def search(request, type="", q="", id=""):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.group.models import Group
        wgs = Group.objects.filter(type="wg").exclude(acronym="2000").select_related().order_by("acronym")
    else:
        wgs = IETFWG.objects.filter(group_type__group_type_id=1).exclude(group_acronym__acronym='2000').select_related().order_by('acronym.acronym')
    args = request.REQUEST.items()
    if args:
        for key, value in args:
            if key == "option":
                type = value
            if re.match(".*search", key):
                q = value
            if re.match(".*id", key):
                id = value
        if type and q or id:
            #log("Got query: type=%s, q=%s, id=%s" % (type, q, id))

            # Search by RFC number or draft-identifier
            # Document list with IPRs
            if type in ["document_search", "rfc_search"]:
                doc = q
                if type == "document_search":
                    if q:
                        q = normalize_draftname(q)
                        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                            from ietf.doc.proxy import DraftLikeDocAlias
                            start = DraftLikeDocAlias.objects.filter(name__contains=q, name__startswith="draft")
                        else:
                            start = InternetDraft.objects.filter(filename__contains=q)
                    if id:
                        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                            from ietf.doc.proxy import DraftLikeDocAlias
                            start = DraftLikeDocAlias.objects.filter(name=id)
                        else:
                            try:
                                id = int(id,10)
                            except:
                                id = -1
                            start = InternetDraft.objects.filter(id_document_tag=id)
                if type == "rfc_search":
                    if q:
                        try:
                            q = int(q, 10)
                        except:
                            q = -1
                        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                            from ietf.doc.proxy import DraftLikeDocAlias
                            start = DraftLikeDocAlias.objects.filter(name__contains=q, name__startswith="rfc")
                        else:
                            start = Rfc.objects.filter(rfc_number=q)
                if start.count() == 1:
                    first = start[0]
                    doc = str(first)
                    # get all related drafts, then search for IPRs on all

                    docs = related_docs(first, [])
                    #docs = get_doclist.get_doclist(first)
                    iprs, docs = iprs_from_docs(docs)
                    return render("ipr/search_doc_result.html", {"q": q, "first": first, "iprs": iprs, "docs": docs, "doc": doc },
                                  context_instance=RequestContext(request) )
                elif start.count():
                    return render("ipr/search_doc_list.html", {"q": q, "docs": start },
                                  context_instance=RequestContext(request) )                        
                else:
                    return render("ipr/search_doc_result.html", {"q": q, "first": {}, "iprs": {}, "docs": {}, "doc": doc },
                                  context_instance=RequestContext(request) )

            # Search by legal name
            # IPR list with documents
            elif type == "patent_search":
                iprs = IprDetail.objects.filter(legal_name__icontains=q, status__in=[1,3]).order_by("-submitted_date", "-ipr_id")
                count = iprs.count()
                iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
                # Some extra information, to help us render 'and' between the
                # last two documents in a sequence
                mark_last_doc(iprs)
                return render("ipr/search_holder_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by content of email or pagent_info field
            # IPR list with documents
            elif type == "patent_info_search":
                if len(q) < 3:
                    return render("ipr/search_error.html", {"q": q, "error": "The search string must contain at least three characters" },
                                  context_instance=RequestContext(request) )
                digits = re.search("[0-9]", q)
                if not digits:
                    return render("ipr/search_error.html", {"q": q, "error": "The search string must contain at least one digit" },
                                  context_instance=RequestContext(request) )
                iprs = []
                for ipr in IprDetail.objects.filter(status__in=[1,3]):
                    if ((q in ipr.patents) |
                        patent_file_search(ipr.legacy_url_0, q) |
                        patent_file_search(ipr.legacy_url_1, q) |
                        patent_file_search(ipr.legacy_url_2, q) ):
                        iprs.append(ipr)
                count = len(iprs)
                iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
                # Some extra information, to help us render 'and' between the
                # last two documents in a sequence
                iprs.sort(key=lambda x: x.ipr_id, reverse=True) # Reverse sort                
                mark_last_doc(iprs)
                return render("ipr/search_patent_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by wg acronym
            # Document list with IPRs
            elif type == "wg_search":
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    from ietf.doc.proxy import DraftLikeDocAlias
                    try:
                        docs = list(DraftLikeDocAlias.objects.filter(document__group__acronym=q))
                        docs += list(DraftLikeDocAlias.objects.filter(document__relateddocument__target__in=docs, document__relateddocument__relationship="replaces"))
                    except:
                        docs = []
                else:
                    try:
                        docs = list(InternetDraft.objects.filter(group__acronym=q))
                    except:
                        docs = []
                    docs += [ draft.replaced_by for draft in docs if draft.replaced_by_id ]
                    docs += list(Rfc.objects.filter(group_acronym=q))

                docs = [ doc for doc in docs if doc.ipr.count() ]
                iprs, docs = iprs_from_docs(docs)
                count = len(iprs)
                return render("ipr/search_wg_result.html", {"q": q, "docs": docs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by rfc and id title
            # Document list with IPRs
            elif type == "title_search":
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    from ietf.doc.proxy import DraftLikeDocAlias
                    try:
                        docs = list(DraftLikeDocAlias.objects.filter(document__title__icontains=q))
                    except:
                        docs = []
                else:
                    try:
                        docs = list(InternetDraft.objects.filter(title__icontains=q))
                    except:
                        docs = []
                    docs += list(Rfc.objects.filter(title__icontains=q))

                docs = [ doc for doc in docs if doc.ipr.count() ]
                iprs, docs = iprs_from_docs(docs)
                count = len(iprs)
                return render("ipr/search_doctitle_result.html", {"q": q, "docs": docs, "count": count },
                                  context_instance=RequestContext(request) )


            # Search by title of IPR disclosure
            # IPR list with documents
            elif type == "ipr_title_search":
                iprs = IprDetail.objects.filter(title__icontains=q, status__in=[1,3]).order_by("-submitted_date", "-ipr_id")
                count = iprs.count()
                iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
                # Some extra information, to help us render 'and' between the
                # last two documents in a sequence
                mark_last_doc(iprs)
                return render("ipr/search_iprtitle_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            else:
                raise Http404("Unexpected search type in IPR query: %s" % type)
        return django.http.HttpResponseRedirect(request.path)

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        for wg in wgs:
            wg.group_acronym = wg # proxy group_acronym for select box
    return render("ipr/search.html", {"wgs": wgs}, context_instance=RequestContext(request))
