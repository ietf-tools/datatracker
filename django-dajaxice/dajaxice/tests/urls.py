from django.conf.urls.defaults import *

from dajaxice.core import dajaxice_autodiscover, dajaxice_config

dajaxice_autodiscover()

urlpatterns = patterns('',
    #Dajaxice URLS
    url(dajaxice_config.dajaxice_url, include('dajaxice.urls')),
)
