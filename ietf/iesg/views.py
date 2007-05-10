# Create your views here.
from django.views.generic.date_based import archive_index
from ietf.idtracker.models import BallotInfo, IDInternal, InternetDraft
import datetime 

def display_recent(request):
  date_threshold = datetime.datetime.now().date() - datetime.timedelta(days=185)
  queryset_ann = BallotInfo.objects.all()
  queryset_list = InternetDraft.objects.all().filter(b_approve_date__gte = date_threshold, intended_status__in=[1,2,6,7]) 
  ann_detail = {
    'queryset': queryset_list,
    'date_field': 'b_approve_date', 
  }
  queryset_list_doc = InternetDraft.objects.all().filter(b_approve_date__gte = date_threshold, intended_status__in=[3,5]).select_related().order_by("-b_approve_date")
  ann_archive = dict(ann_detail, allow_empty=True, num_latest=15000, extra_context={'is_recent':1,'queryset_doc':queryset_list_doc, 'title_prefix':'Recent'},template_name='iesg/ann/ietf_doc.html')                             
  return archive_index(queryset_list,'b_approve_date',{ 'allow_empty':True })

