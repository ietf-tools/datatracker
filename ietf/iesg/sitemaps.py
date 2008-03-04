# Copyright The IETF Trust 2007, All Rights Reserved
#
from django.contrib.sitemaps import GenericSitemap
from ietf.iesg.urls import telechat_detail

IESGMinutesMap = GenericSitemap(telechat_detail, changefreq="never")
