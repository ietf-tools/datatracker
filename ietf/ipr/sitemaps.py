# Copyright The IETF Trust 2007-2023, All Rights Reserved
#
from django.conf import settings
from django.contrib.sitemaps import GenericSitemap
from ietf.ipr.models import IprDisclosureBase

# changefreq is "never except when it gets updated or withdrawn"
# so skip giving one

queryset = IprDisclosureBase.objects.filter(state__in=settings.PUBLISH_IPR_STATES)
archive = {'queryset':queryset, 'date_field': 'time', 'allow_empty':True }
IPRMap = GenericSitemap(archive)        # type: ignore
