from django.conf import settings

from ietf.stats import views
from ietf.utils.urls  import url

urlpatterns = [
    url("^$", views.stats_index),
    url("^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views.review_stats),
]
