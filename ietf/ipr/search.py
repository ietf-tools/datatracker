# Copyright The IETF Trust 2007, All Rights Reserved

import codecs
import re
import os.path
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response as render
from django.template import RequestContext
from django.conf import settings
from ietf.ipr.models import IprDraft, IprDetail
from ietf.ipr.related import related_docs
from ietf.utils import log, normalize_draftname
from ietf.group.models import Group
from ietf.doc.models import DocAlias


def mark_last_doc(iprs):
    for item in iprs:
        docs = item.docs()
        count = len(docs)
        if count > 1:
            item.last_draft = docs[count-1]

def iprs_from_docs(docs):
    iprs = []
    for doc in docs:
        from ietf.ipr.models import IprDocAlias
        disclosures = [ x.ipr for x in IprDocAlias.objects.filter(doc_alias=doc, ipr__status__in=[1,3]) ]
        doc.iprs = None
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
    wgs = Group.objects.filter(type="wg").select_related().order_by("acronym")
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
                        start = DocAlias.objects.filter(name__contains=q, name__startswith="draft")
                    if id:
                        start = DocAlias.objects.filter(name=id)
                if type == "rfc_search":
                    if q:
                        try:
                            q = int(q, 10)
                        except:
                            q = -1
                        start = DocAlias.objects.filter(name__contains=q, name__startswith="rfc")
                if start.count() == 1:
                    first = start[0]
                    doc = str(first)
                    docs = related_docs(first)
                    iprs, docs = iprs_from_docs(docs)
                    iprs.sort(key=lambda x:(x.submitted_date,x.ipr_id))
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
                docs = list(DocAlias.objects.filter(document__group__acronym=q))
                related = []
                for doc in docs:
                    doc.product_of_this_wg = True
                    related += related_docs(doc)

                iprs, docs = iprs_from_docs(list(set(docs+related)))
                docs = [ doc for doc in docs if doc.iprs ]
                docs = sorted(docs,key=lambda x: max([ipr.submitted_date for ipr in x.iprs]),reverse=True)
                   
                count = len(iprs)
                return render("ipr/search_wg_result.html", {"q": q, "docs": docs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by rfc and id title
            # Document list with IPRs
            elif type == "title_search":
                docs = list(DocAlias.objects.filter(document__title__icontains=q))
                related = []
                for doc in docs:
                    related += related_docs(doc)

                iprs, docs = iprs_from_docs(list(set(docs+related)))
                docs = [ doc for doc in docs if doc.iprs ]
                docs = sorted(docs,key=lambda x: max([ipr.submitted_date for ipr in x.iprs]),reverse=True)

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
        return HttpResponseRedirect(request.path)

    return render("ipr/search.html", {"wgs": wgs}, context_instance=RequestContext(request))
