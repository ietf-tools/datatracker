# Copyright The IETF Trust 2023, All Rights Reserved

from ietf.api import views_dashboard

from ietf.utils.urls import url

urlpatterns = [
    url(r'^groups_opened_closed/(?P<groupType>[a-z]+)/(?P<startYear>\d{4})/(?P<endYear>\d{4})/$', views_dashboard.groups_opened_closed),
    url(r'^submissions/(?P<start>\d{4}-\d{1,2})/(?P<end>\d{4}-\d{1,2})', views_dashboard.submissions),
]


