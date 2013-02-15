from ietf.ipr.models import IprDetail

class _IprDetailManager(object):
    def queue_ipr(self):
#        qq{select document_title, ipr_id, submitted_date,status from ipr_detail where status = 0 order by submitted_date desc};
        return IprDetail.objects.filter(status=0).order_by('-submitted_date')

    def generic_ipr(self):
        #qq{select document_title, ipr_id, submitted_date,status,additional_old_title1,additional_old_url1,additional_old_title2,additional_old_url2 from ipr_detail where status = 1 and generic=1 and third_party=0 order by submitted_date desc};
        return IprDetail.objects.filter(status=1, generic=True, third_party=False).order_by('-submitted_date')

    def third_party_notifications(self):
        #qq{select document_title, ipr_id, submitted_date,status,additional_old_title1,additional_old_url1,additional_old_title2,additional_old_url2 from ipr_detail where status = 1 and third_party=1 order by submitted_date desc};
        return IprDetail.objects.filter(status=1, third_party=True).order_by('-submitted_date')

    def specific_ipr(self):
        # qq{select document_title, ipr_id, submitted_date,status,additional_old_title1,additional_old_url1,additional_old_title2,additional_old_url2 from ipr_detail where status = 1 and generic=0 and third_party=0 order by submitted_date desc};
        return IprDetail.objects.filter(status=1, generic=False, third_party=False).order_by('-submitted_date')

    def admin_removed_ipr(self):
        #qq{select document_title, ipr_id, submitted_date,status,additional_old_title1,additional_old_url1,additional_old_title2,additional_old_url2 from ipr_detail where status = 2 order by submitted_date desc};
        return IprDetail.objects.filter(status=2).order_by('-submitted_date')

    def request_removed_ipr(self):
        #qq{select document_title, ipr_id, submitted_date,status,additional_old_title1,additional_old_url1,additional_old_title2,additional_old_url2 from ipr_detail where status = 3 order by submitted_date desc};
        return IprDetail.objects.filter(status=3).order_by('-submitted_date')

IprDetailManager = _IprDetailManager()
