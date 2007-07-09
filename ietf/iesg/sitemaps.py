from django.contrib.sitemaps import Sitemap, GenericSitemap
from ietf.iesg.models import TelechatMinutes
from ietf.iesg.urls import telechat_detail

IESGMinutesMap = GenericSitemap(telechat_detail, changefreq="never")
