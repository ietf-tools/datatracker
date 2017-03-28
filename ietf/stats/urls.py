from django.conf import settings

from ietf.stats import views
from ietf.utils.urls  import url

urlpatterns = [
    url("^$", views.stats_index),
    url("^document/(?:(?P<stats_type>authors|pages|words|format|formlang|author/(?:documents|affiliation|country|continent|citations|hindex)|yearly/(?:affiliation|country|continent))/)?$", views.document_stats),
    url("^knowncountries/$", views.known_countries_list),
    url("^review/(?:(?P<stats_type>completion|results|states|time)/)?(?:%(acronym)s/)?$" % settings.URL_REGEXPS, views.review_stats),
]
