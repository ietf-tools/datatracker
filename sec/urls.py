from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^mysite/', include('mysite.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    url(r'^$', direct_to_template, {'template': 'main.html'}, name="home"),
    (r'^announcement/', include('sec.announcement.urls')),
    (r'^areas/', include('sec.areas.urls')),
    (r'^drafts/', include('sec.drafts.urls')),
    (r'^groups/', include('sec.groups.urls')),
    (r'^ipr/', include('sec.ipr.urls')),
    (r'^meetings/', include('sec.meetings.urls')),
    (r'^proceedings/', include('sec.proceedings.urls')),
    (r'^rolodex/', include('sec.rolodex.urls')),
    (r'^sreq/', include('sec.sreq.urls')),
    (r'^telechat/', include('sec.telechat.urls')),
)
