from django.contrib.sitemaps import GenericSitemap
from ietf.ipr.urls import archive

# changefreq is "never except when it gets updated or withdrawn"
# so skip giving one
IPRMap = GenericSitemap(archive)
