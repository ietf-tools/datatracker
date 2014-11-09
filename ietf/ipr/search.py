# Copyright The IETF Trust 2007, All Rights Reserved

import codecs
import re
import os.path

from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response as render
from django.template import RequestContext
from django.conf import settings
from django.db.models import Q


from ietf.ipr.models import IprDocAlias, IprDetail
from ietf.ipr.related import related_docs
from ietf.utils.draft_search import normalize_draftname
from ietf.group.models import Group
from ietf.doc.models import DocAlias


def iprs_from_docs(docs):
    iprs = []
    for doc in docs:
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
            file.close()
            return q in text
    return False

def search(request):
    wgs = Group.objects.filter(Q(type="wg") | Q(type="rg")).select_related().order_by("acronym")

    search_type = request.GET.get("option")
    if search_type:
        docid = request.GET.get("id") or request.GET.get("id_document_tag") or ""

        q = ""
        for key, value in request.GET.items():
            if key.endswith("search"):
                q = value

        if search_type and (q or docid):
            # Search by RFC number or draft-identifier
            # Document list with IPRs
            if search_type in ["document_search", "rfc_search"]:
                doc = q

                if docid:
                    start = DocAlias.objects.filter(name=docid)
                else:
                    if search_type == "document_search":
                        q = normalize_draftname(q)
                        start = DocAlias.objects.filter(name__contains=q, name__startswith="draft")
                    elif search_type == "rfc_search":
                        start = DocAlias.objects.filter(name="rfc%s" % q.lstrip("0"))

                if len(start) == 1:
                    first = start[0]
                    doc = str(first)
                    docs = related_docs(first)
                    iprs, docs = iprs_from_docs(docs)
                    iprs.sort(key=lambda x: (x.submitted_date, x.ipr_id))
                    return render("ipr/search_doc_result.html", {"q": q, "iprs": iprs, "docs": docs, "doc": doc },
                                  context_instance=RequestContext(request) )
                elif start:
                    return render("ipr/search_doc_list.html", {"q": q, "docs": start },
                                  context_instance=RequestContext(request) )                        
                else:
                    return render("ipr/search_doc_result.html", {"q": q, "iprs": {}, "docs": {}, "doc": doc },
                                  context_instance=RequestContext(request) )

            # Search by legal name
            # IPR list with documents
            elif search_type == "patent_search":
                iprs = IprDetail.objects.filter(legal_name__icontains=q, status__in=[1,3]).order_by("-submitted_date", "-ipr_id")
                count = len(iprs)
                iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
                return render("ipr/search_holder_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by patents field or content of emails for patent numbers
            # IPR list with documents
            elif search_type == "patent_info_search":
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
                iprs.sort(key=lambda x: x.ipr_id, reverse=True)
                return render("ipr/search_patent_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            # Search by wg acronym
            # Document list with IPRs
            elif search_type == "wg_search":
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
            elif search_type == "title_search":
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
            elif search_type == "ipr_title_search":
                iprs = IprDetail.objects.filter(title__icontains=q, status__in=[1,3]).order_by("-submitted_date", "-ipr_id")
                count = iprs.count()
                iprs = [ ipr for ipr in iprs if not ipr.updated_by.all() ]
                return render("ipr/search_iprtitle_result.html", {"q": q, "iprs": iprs, "count": count },
                                  context_instance=RequestContext(request) )

            else:
                raise Http404("Unexpected search type in IPR query: %s" % search_type)
        return HttpResponseRedirect(request.path)

    return render("ipr/search.html", {"wgs": wgs}, context_instance=RequestContext(request))
