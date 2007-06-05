# Create your views here.
#from django.views.generic.date_based import archive_index
from ietf.idtracker.models import IDInternal, InternetDraft
from django.views.generic.list_detail import object_list
from django.http import Http404
import datetime 

date_threshold = datetime.datetime.now().date() - datetime.timedelta(days=185)

def inddocs(request):
   queryset_list_ind = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,noproblem=1, dnp=0).select_related().order_by('-internet_drafts.b_approve_date')
   queryset_list_ind_dnp = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,dnp=1).order_by('-dnp_date')
   return object_list(request, queryset=queryset_list_ind, template_name='iesg/independent_doc.html', allow_empty=True, extra_context={'object_list_dnp':queryset_list_ind_dnp })

def wgdocs(request,cat):
   is_recent = 0
   if cat == 'recent':
      is_recent = 1
      queryset_list = InternetDraft.objects.filter(b_approve_date__gte = date_threshold, intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0).order_by("-b_approve_date")
      queryset_list_doc = InternetDraft.objects.filter(b_approve_date__gte = date_threshold, intended_status__in=[3,5],idinternal__via_rfc_editor=0).order_by("-b_approve_date")
   elif cat == 'previous':
      queryset_list = InternetDraft.objects.filter(b_approve_date__lt = date_threshold, b_approve_date__gte = '1998-10-15', intended_status__in=[1,2,6,7]).order_by("-b_approve_date")
      queryset_list_doc = InternetDraft.objects.filter(b_approve_date__lt = date_threshold, b_approve_date__gte = '1998-10-15', intended_status__in=[3,5]).order_by("-b_approve_date")
   else:
     raise Http404
   return object_list(request, queryset=queryset_list, template_name='iesg/ietf_doc.html', allow_empty=True, extra_context={'object_list_doc':queryset_list_doc, 'is_recent':is_recent })

