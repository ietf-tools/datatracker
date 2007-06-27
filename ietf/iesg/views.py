# Copyright The IETF Trust 2007, All Rights Reserved

# Create your views here.
#from django.views.generic.date_based import archive_index
from ietf.idtracker.models import IDInternal, InternetDraft
from django.views.generic.list_detail import object_list
from django.http import Http404
from django.template import RequestContext
from django.shortcuts import render_to_response
import datetime 

def date_threshold():
    """Return the first day of the month that is 185 days ago."""
    ret = datetime.date.today() - datetime.timedelta(days=185)
    ret = ret - datetime.timedelta(days=ret.day - 1)
    return ret

def inddocs(request):
   queryset_list_ind = InternetDraft.objects.filter(idinternal__via_rfc_editor=1, idinternal__rfc_flag=0, idinternal__noproblem=1, idinternal__dnp=0).order_by('-b_approve_date')
   queryset_list_ind_dnp = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,dnp=1).order_by('-dnp_date')
   return object_list(request, queryset=queryset_list_ind, template_name='iesg/independent_doc.html', allow_empty=True, extra_context={'object_list_dnp':queryset_list_ind_dnp })

def wgdocs(request,cat):
   is_recent = 0
   queryset_list=[]
   queryset_list_doc=[]
   if cat == 'new':
      is_recent = 1
      queryset = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[3,5],idinternal__via_rfc_editor=0, idinternal__primary_flag=1).order_by("-b_approve_date")
   elif cat == 'prev':
      queryset = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1997-12-1', intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1998-10-15', intended_status__in=[3,5],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
   else:
     raise Http404
   for item in list(queryset):
      queryset_list.append(item)
      try:
        ballot_id=item.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list.append(sub_item)
   for item2 in list(queryset_doc):
      queryset_list_doc.append(item2)
      try:
        ballot_id=item2.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item2 in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list_doc.append(sub_item2)
   return render_to_response( 'iesg/ietf_doc.html', {'object_list': queryset_list, 'object_list_doc':queryset_list_doc, 'is_recent':is_recent}, context_instance=RequestContext(request) )

