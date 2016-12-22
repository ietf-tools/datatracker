from django.conf import settings

import ietf.stats.views
from ietf.utils.urls  import url

urlpatterns = [
    url("^$", ietf.stats.views.stats_index),
    url("^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, ietf.stats.views.review_stats),
]
