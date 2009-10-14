# Copyright The IETF Trust 2007, All Rights Reserved
#
from django.contrib.sitemaps import GenericSitemap
from ietf.ipr.models import IprDetail

# changefreq is "never except when it gets updated or withdrawn"
# so skip giving one

queryset = IprDetail.objects.filter(status__in=[1,3])
archive = {'queryset':queryset, 'date_field': 'submitted_date', 'allow_empty':True }
IPRMap = GenericSitemap(archive)
